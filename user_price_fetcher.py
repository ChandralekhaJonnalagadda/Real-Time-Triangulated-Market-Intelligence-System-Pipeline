import json
import boto3
import yfinance as yf
from datetime import datetime

# Setup Clients
dynamodb = boto3.resource("dynamodb")
table_name = "UserTickers"
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    params = event.get("queryStringParameters")or {}
    user_id = params.get("user_id")
    
    if not user_id:
        user_id = "U001" 

    try:
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id)
        )
        user_items = result.get("Items", [])
        
        # 1. CURRENCY PREDICTIVE LOGIC (Requirement #8)
        forex = yf.Ticker("USDINR=X")
        fx_hist = forex.history(period="30d")
        current_fx = fx_hist['Close'].iloc[-1]
        sma5 = fx_hist['Close'].tail(5).mean()
        sma20 = fx_hist['Close'].tail(20).mean()
        
        # Predictive Logic: If 5-day average is higher than 20-day, trend is UP (Wait to convert)
        fx_advice = "WAIT - Upward Trend" if sma5 > sma20 else "CONVERT NOW - Downward Trend"

        portfolio_data = []
        global_earnings_calendar = []

        for item in user_items:
            symbol = item['ticker']
            stock = yf.Ticker(symbol)
            info = stock.info

            sentiment = item.get('recent_news_sentiment', 'NEUTRAL')
            source_label = "standard feeds"
            
            # Fetch 1 year to ensure we have enough data for All-Time High/Low and 200MA
            history = stock.history(period="1y") 
            hist_6m = history.tail(126)
            
            stock = yf.Ticker(symbol)

            # 2. STRENGTH/WEAKNESS ANALYSIS (Requirement #4)
            margins = info.get("operatingMargins", 0) or 0
            rev_growth = info.get("revenueGrowth", 0) or 0
            strength_weakness = "Strength: High Margins" if margins > 0.15 else "Weakness: Low Margins"
            if rev_growth > 0.05: strength_weakness += " & Solid Growth"


            # Technical Indicators
            ma50 = history['Close'].rolling(window=50).mean().iloc[-1] if len(history) >= 50 else 0
            ma200 = history['Close'].rolling(window=200).mean().iloc[-1] if len(history) >= 200 else 0
            
            est_status = "EXCEED" if info.get("trailingEps", 0) > 0 and rev_growth > 0 else "MISS"
            # Price Extremes
            ath = history['High'].max()
            atl = history['Low'].min()
            h52 = info.get("fiftyTwoWeekHigh")
            l52 = info.get("fiftyTwoWeekLow")
            
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0

            
            # 30-Day Earnings Logic
            calendar = stock.calendar
            earnings_date_str = "TBD"
            if calendar and isinstance(calendar, dict):
                raw_date = calendar.get('Earnings Date', [None])[0]
                if raw_date:
                    earnings_date_str = str(raw_date)
                    target_date = raw_date.date() if hasattr(raw_date, 'date') else raw_date
                    days_until = (target_date - datetime.now().date()).days
                    if 0 <= days_until <= 30:
                        global_earnings_calendar.append({"ticker": symbol, "date": earnings_date_str, "days_left": days_until})

            # Geopolitical Sentinel
            news = stock.news[:5]
            risk_score = 0
            risk_keywords = {"war": 30, "tariff": 25, "sanction": 25, "election": 15, "trade": 10}
            for n in news:
                title = n.get('title', '').lower()
                for word, weight in risk_keywords.items():
                    if word in title: risk_score += weight
            
            geo_status = "STABLE" if risk_score < 30 else "ELEVATED" if risk_score < 60 else "CRITICAL"

            # Recommendation Logic
            pe = info.get("trailingPE", 0)
            recommendation = "HOLD"
            if current_price > ma200 and (pe and pe < 25): recommendation = "BUY"
            elif current_price < ma200 * 0.98: recommendation = "SELL"

            ai_insight = (f"VALUATION: {'Fair' if pe < 25 else 'High'}. "f"NEWS: {sentiment} ({source_label}). "f"Strategy: Monitor earnings on {earnings_date_str}.")

            portfolio_data.append({
                "ticker": symbol,
                "sentiment": sentiment,
                "current_price": current_price,
                "strength_weakness": strength_weakness,
                "chart_data" : list(hist_6m['Close']),
                "chart_labels": [d.strftime('%b %d,%Y') for d in hist_6m.index],
                "recommendation": recommendation,
                "tech": {
                    "ma50": ma50,
                    "ma200": ma200,
                    "ath": ath,
                    "atl": atl,
                    "h52": h52,
                    "l52": l52,
                    "stop_loss": ma200 * 0.98
                },
                "fundamentals": {
                    "pe": pe,
                    "eps": info.get("trailingEps"),
                    "debt": info.get("totalDebt"),
                    "cash_flow": info.get("freeCashflow"),
                    "earnings_status": "EXCEEDED" if (info.get("trailingEps", 0) > info.get("forwardEps", 0)) else "MEETS"
                },
                "geo_status": geo_status,
                "geo_risk_score": risk_score,
                "earnings_date": earnings_date_str,
                "ai_insight": ai_insight
            })

        return response(200, {
            "portfolio": portfolio_data,
            "currency": {"rate": current_fx, "advice": fx_advice},
            "server_time": datetime.now().isoformat(),
            "earnings_calendar_30d": sorted(global_earnings_calendar, key=lambda x: x['days_left']),
            "forex": yf.Ticker("USDINR=X").info.get("regularMarketPrice"),
            "fx_advice": fx_advice,
            "last_sync": datetime.now().strftime("%H:%M:%S")
        })
    except Exception as e:
        return response(500, {"error": str(e)})

def response(status_code, body):
    return {"statusCode": status_code, "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}, "body": json.dumps(body, default=str)}
