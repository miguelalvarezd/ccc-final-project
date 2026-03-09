import json
import boto3
import os
import urllib.parse
from datetime import datetime

# Initialize clients outside the handler to reuse connections
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Initialize IoT client for MQTT publishing
# Note: In production, you may need to specify your specific IoT Core endpoint URL here.
iot_endpoint_url = os.environ.get('IOT_ENDPOINT') # e.g., 'a1b2c3d4e5f6g7-ats.iot.eu-west-1.amazonaws.com'
iot_client = boto3.client('iot-data', endpoint_url=f"https://{iot_endpoint_url}")

def lambda_handler(event, context):
    gold_bucket = os.environ.get('GOLD_BUCKET_NAME')
    table_name = os.environ.get('DYNAMODB_TABLE_NAME')
    lot_id = os.environ.get('LOT_ID', 'LOT#pi-zone-A') 
    
    if not gold_bucket or not table_name:
        raise ValueError("Missing essential environment variables (GOLD_BUCKET_NAME or DYNAMODB_TABLE_NAME).")
        
    table = dynamodb.Table(table_name)

    for record in event.get('Records', []):
        bronze_bucket = record['s3']['bucket']['name']
        file_key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        try:
            # 1. Fetch the raw payload
            response = s3_client.get_object(Bucket=bronze_bucket, Key=file_key)
            raw_payload = json.loads(response['Body'].read().decode('utf-8'))
            
            device_id = raw_payload.get("device_id")
            sensor_id = raw_payload.get("sensor_id")
            is_occupied = raw_payload.get("is_occupied", False)
            occupancy_type = raw_payload.get("occupancy_type", "unknown")
            full_timestamp = raw_payload.get("timestamp")
            
            # 2. Extract Date/Time
            date_part, time_part = full_timestamp.replace('Z', '').split('T')
            dt_obj = datetime.strptime(full_timestamp, "%Y-%m-%dT%H:%M:%SZ")
            year, month, day = dt_obj.strftime("%Y"), dt_obj.strftime("%m"), dt_obj.strftime("%d")

            # 3. Fetch DynamoDB State
            meta_response = table.get_item(Key={'LotID': lot_id, 'EntityID': 'METADATA'})
            meta_item = meta_response.get('Item', {})
            lot_physical_capacity = int(meta_item.get('TotalCapacity', 14)) 
            spots_under_repair = int(meta_item.get('SpotsUnderRepair', 0))
            lot_usable_spaces = lot_physical_capacity - spots_under_repair

            spot_response = table.get_item(Key={'LotID': lot_id, 'EntityID': f'SPOT#{sensor_id}'})
            spot_item = spot_response.get('Item', {})
            
            # Extract Reservation State and New Fields
            reservation_state = spot_item.get('ReservationState', 'AVAILABLE')
            license_plate = spot_item.get('LicensePlate')
            booked_until = spot_item.get('BookedUntil')

            # 4. State Logic
            final_status = "UNKNOWN"
            if is_occupied:
                if reservation_state == "AVAILABLE":
                    final_status = "OCCUPIED"
                elif reservation_state == "BOOKED":
                    final_status = "OCCUPIED_BUT_BOOKED"
                elif reservation_state == "MAINTENANCE":
                    final_status = "OCCUPIED_MAINTENANCE"
            else:
                if reservation_state == "AVAILABLE":
                    final_status = "FREE"
                elif reservation_state == "BOOKED":
                    final_status = "BOOKED_WAITING" 
                elif reservation_state == "MAINTENANCE":
                    final_status = "MAINTENANCE"

            print(f"[DEBUG] Final Status is: {final_status}")
            
            # 5. Alerting via MQTT
            if final_status in ["OCCUPIED_BUT_BOOKED", "OCCUPIED_MAINTENANCE"]:
                print(f"ALERT: Sensor {sensor_id} reported an invalid occupancy state ({final_status})!")
                status_send = "BOOKED" if final_status == "OCCUPIED_BUT_BOOKED" else "MAINTENANCE"
                # Build the MQTT payload
                mqtt_payload = {
                    "error": status_send,
                    "sensor_id": sensor_id,
                    "timestamp": full_timestamp
                }
                
                # Inject reservation details if someone parked in a booked spot
                if final_status == "OCCUPIED_BUT_BOOKED":
                    mqtt_payload["expected_license_plate"] = license_plate
                    mqtt_payload["booked_until"] = booked_until

                # Publish to IoT Core
                iot_client.publish(
                    topic=f"esp32/sub",
                    qos=1,
                    payload=json.dumps(mqtt_payload)
                )

                print("[DEBUG] Published MQTT topic")

            # 6. Build the Enriched Gold Payload
            gold_payload = {
                "device_id": device_id,
                "sensor_id": sensor_id,
                "occupancy_type": occupancy_type,            
                "status": final_status,                      
                "is_physically_occupied": is_occupied,       
                "db_reservation_state": reservation_state,
                "license_plate": license_plate,              # Added to Data Lake
                "booked_until": booked_until,                # Added to Data Lake
                "event_timestamp": full_timestamp,
                "event_date": date_part,
                "event_time": time_part,
                "lot_physical_capacity": lot_physical_capacity,
                "lot_usable_spaces": lot_usable_spaces,
                "processed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            }

            # 7. Save to Gold S3 Bucket
            filename = os.path.basename(file_key).replace("raw", "processed")
            gold_key = f"year={year}/month={month}/day={day}/{filename}"

            s3_client.put_object(
                Bucket=gold_bucket,
                Key=gold_key,
                Body=json.dumps(gold_payload),
                ContentType='application/json'
            )
            print(f"Successfully saved to Gold: {gold_key}")

        except Exception as e:
            print(f"Error processing {file_key}: {str(e)}")
            raise e

    return {
        'statusCode': 200,
        'body': 'Successfully enriched Bronze files and moved to Gold.'
    }