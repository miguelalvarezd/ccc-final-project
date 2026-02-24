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
            # NOTE: In reality, you would query your DynamoDB Metadata table here.
            # For this script, we use a mock dictionary to represent what the DB returns:
            simulated_db_data = {
                "lot_physical_capacity": 50,
                "spots_under_repair": 2, 
                "currently_parked_cars": 38 
            }
            
            # Calculate the true capacity
            usable_capacity = simulated_db_data["lot_physical_capacity"] - simulated_db_data["spots_under_repair"]
            
            # Adjust the parked cars count based on this new event
            is_occupied = raw_payload.get('is_occupied', False)
            if is_occupied:
                simulated_db_data["currently_parked_cars"] += 1
            else:
                simulated_db_data["currently_parked_cars"] -= 1
                
            # Calculate the final available spaces
            available_spaces = usable_capacity - simulated_db_data["currently_parked_cars"]

            # 4. Build the Enriched Gold Payload
            gold_payload = {
                "device_id": raw_payload.get("device_id"),
                "sensor_id": raw_payload.get("sensor_id"),
                "status": "OCCUPIED" if is_occupied else "FREE",
                "event_timestamp": full_timestamp,
                "event_date": date_part,
                "event_time": time_part,
                "lot_physical_capacity": simulated_db_data["lot_physical_capacity"],
                "lot_usable_capacity": usable_capacity,
                "lot_available_spaces": available_spaces,
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