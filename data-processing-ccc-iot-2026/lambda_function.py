import json
import boto3
import os
import urllib.parse
from datetime import datetime

# Initialize the S3 client
s3_client = boto3.client('s3')

# In a full production setup, you would initialize DynamoDB here
# dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    # Fetch the destination Gold bucket name from Environment Variables
    gold_bucket = os.environ.get('GOLD_BUCKET_NAME')
    if not gold_bucket:
        raise ValueError("GOLD_BUCKET_NAME environment variable is missing.")

    # S3 triggers send events in a 'Records' list
    for record in event.get('Records', []):
        bronze_bucket = record['s3']['bucket']['name']
        file_key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        try:
            # 1. Fetch the raw payload from the Bronze bucket
            response = s3_client.get_object(Bucket=bronze_bucket, Key=file_key)
            raw_payload = json.loads(response['Body'].read().decode('utf-8'))

            # 2. Extract and Split the Date/Time
            # Expecting format: "2026-02-23T18:37:00Z"
            full_timestamp = raw_payload.get('timestamp')
            
            # Create the separate event_date and event_time fields
            date_part, time_part = full_timestamp.replace('Z', '').split('T')

            # Parse to datetime object for building the S3 folder partitions
            dt_obj = datetime.strptime(full_timestamp, "%Y-%m-%dT%H:%M:%SZ")
            year, month, day = dt_obj.strftime("%Y"), dt_obj.strftime("%m"), dt_obj.strftime("%d")

            # 3. Handle Capacity and Availability Logic
            # Lot-level configuration from environment variables
            lot_physical_capacity = int(os.environ.get('LOT_PHYSICAL_CAPACITY', '14'))
            spots_under_repair = int(os.environ.get('SPOTS_UNDER_REPAIR', '0'))

            # Usable capacity = total physical spots minus those out of service
            lot_usable_spaces = lot_physical_capacity - spots_under_repair

            # 4. Build the Enriched Gold Payload
            is_occupied = raw_payload.get('is_occupied', False)

            gold_payload = {
                "device_id": raw_payload.get("device_id"),
                "sensor_id": raw_payload.get("sensor_id"),
                "status": "OCCUPIED" if is_occupied else "FREE",
                "event_timestamp": full_timestamp,
                "event_date": date_part,
                "event_time": time_part,
                "lot_physical_capacity": lot_physical_capacity,
                "lot_usable_spaces": lot_usable_spaces,
                "processed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            }

            # 5. Save to the Gold Bucket with Partitioning
            # Strip out any old folder paths from Bronze, just keep the filename
            filename = os.path.basename(file_key).replace("raw", "processed")
            gold_key = f"year={year}/month={month}/day={day}/{filename}"

            s3_client.put_object(
                Bucket=gold_bucket,
                Key=gold_key,
                Body=json.dumps(gold_payload),
                ContentType='application/json'
            )
            print(f"Successfully enriched data and saved to Gold as: {gold_key}")

        except Exception as e:
            print(f"Error processing {file_key} from {bronze_bucket}: {str(e)}")
            raise e

    return {
        'statusCode': 200,
        'body': 'Successfully enriched Bronze files and moved to Gold.'
    }