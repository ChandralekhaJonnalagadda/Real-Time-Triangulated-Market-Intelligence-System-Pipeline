import json
import boto3

# Setup DynamoDB
dynamodb = boto3.resource("dynamodb")
table_name = "UserTickers"
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    method = event.get("httpMethod")
    
    # Enable CORS for browser requests
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

    # Handle Preflight (Browser safety check)
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        # Parse the request body (the ticker and user_id)
        body_raw = event.get("body")
        if body_raw is None:
            body = {}
        else:
            body = json.loads(body_raw)
        
        user_id = body.get("user_id")
        if not user_id:
            user_id = "U001"
        ticker = body.get("ticker", "").strip().upper()
        
        if not ticker:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Ticker is required"})}

        if method == "POST":
            # --- ADD LOGIC ---
            table.put_item(Item={
                "user_id": user_id,
                "ticker": ticker,
                "asset_type": body.get("asset_type", "STOCK"),
            })
            return {
                "statusCode": 200, 
                "headers": headers, 
                "body": json.dumps({"message": f"Successfully added {ticker}"})
            }

        elif method == "DELETE":
            # --- DELETE LOGIC ---
            table.delete_item(Key={
                "user_id": user_id,
                "ticker": ticker
            })
            return {
                "statusCode": 200, 
                "headers": headers, 
                "body": json.dumps({"message": f"Successfully removed {ticker}"})
            }

        else:
            return {"statusCode": 405, "headers": headers, "body": json.dumps({"error": "Method Not Allowed"})}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500, 
            "headers": headers, 
            "body": json.dumps({"error": str(e)})
        }
