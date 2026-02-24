import json
import boto3
import os
import uuid
from datetime import datetime

# Initialize the S3 client
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    # Fetch the destination bucket name from Environment Variables
    bucket_name = os.environ.get('BRONZE_BUCKET_NAME')
    
    if not bucket_name:
        raise ValueError("BRONZE_BUCKET_NAME environment variable is missing.")

    # SQS can send multiple messages in a single batch (event['Records'])
    for record in event.get('Records', []):
        # The raw JSON payload from your Raspberry Pi
        payload = record['body']
        
        # Create a unique filename (e.g., raw_data_20260223_193015_a1b2c3d4.json)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        file_name = f"raw_data_{timestamp}_{unique_id}.json"
        
        try:
            # Upload the raw payload directly to the S3 Bronze bucket
            s3_client.put_object(
                Bucket=bucket_name,
                Key=file_name,
                Body=payload,
                ContentType='application/json'
            )
            print(f"Successfully saved {file_name} to {bucket_name}")
            
        except Exception as e:
            print(f"Error saving message to S3: {str(e)}")
            # Raise the error so SQS knows the message failed and can retry it
            raise e

    return {
        'statusCode': 200,
        'body': 'Successfully processed SQS batch and saved to S3 Bronze.'
    }