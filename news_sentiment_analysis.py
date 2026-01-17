import json
import boto3
import requests
from bs4 import BeautifulSoup

# Clients
dynamodb = boto3.resource('dynamodb')
comprehend = boto3.client('comprehend')
table = dynamodb.Table('UserTickers')

def lambda_handler(event, context):
    tickers_data = table.scan().get('Items', [])
    
    for item in tickers_data:
        ticker = item['ticker']
        urls = item.get('news_urls', ["https://finance.yahoo.com" + ticker])
        
        all_headlines = []
        for url in urls:
            try:
                # 2. Scraping Logic (Requirement #3)
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                soup = BeautifulSoup(response.text, 'html.parser')
                # Find all heading tags (adjust selectors based on specific sites)
                headlines = [h.get_text() for h in soup.find_all(['h1', 'h2', 'h3'])[:5]]
                all_headlines.extend(headlines)
            except Exception as e:
                print(f"Error scraping {url}: {e}")

        if all_headlines:
            # 3. Sentiment Analysis (Requirement #3 Categorization)
            full_text = " ".join(all_headlines)[:4500] # Comprehend limit is 5000 chars
            sentiment_res = comprehend.detect_sentiment(Text=full_text, LanguageCode='en')
            sentiment = sentiment_res['Sentiment'] # POSITIVE, NEGATIVE, or NEUTRAL
            
            # 4. Save back to DynamoDB
            table.update_item(
                Key={'user_id': item['user_id'], 'ticker': ticker},
                UpdateExpression="SET recent_news_sentiment = :s",
                ExpressionAttributeValues={':s': sentiment}
            )

    return {"status": "News sentiment updated"}
