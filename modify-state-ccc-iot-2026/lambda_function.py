import json
import boto3
import os
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')

# Helper for CORS
def make_response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        },
        "body": json.dumps(body_dict)
    }

def lambda_handler(event, context):
    # Handle CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {"ok": True})

    table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'ParkingLotState')
    lot_id = os.environ.get('LOT_ID', 'LOT#pi-zone-A')
    table = dynamodb.Table(table_name)

    try:
        # Parse the incoming JSON body from API Gateway
        body = json.loads(event.get("body", "{}"))
        sensor_id = body.get("sensor_id")
        new_state = body.get("state") # 'AVAILABLE', 'BOOKED', or 'MAINTENANCE'
        
        # Optional fields for booking
        license_plate = body.get("license_plate", None)
        booked_until = body.get("booked_until", None)

        if not sensor_id or not new_state:
            return make_response(400, {"error": "Missing required fields: 'sensor_id' and 'state'"})

        if new_state not in ['AVAILABLE', 'BOOKED', 'MAINTENANCE']:
            return make_response(400, {"error": f"Invalid state: {new_state}"})

        # 1. Fetch current spot state to see if we are entering or leaving MAINTENANCE
        current_spot = table.get_item(Key={'LotID': lot_id, 'EntityID': f'SPOT#{sensor_id}'}).get('Item', {})
        old_state = current_spot.get('ReservationState', 'AVAILABLE')

        # 2. Update the specific Spot
        update_expr = "SET ReservationState = :s"
        expr_attr_vals = {':s': new_state}
        
        # Add optional booking details if provided, or remove them if freeing the spot
        if new_state == "BOOKED":
            if license_plate:
                update_expr += ", LicensePlate = :lp"
                expr_attr_vals[':lp'] = license_plate
            if booked_until:
                update_expr += ", BookedUntil = :bu"
                expr_attr_vals[':bu'] = booked_until
        elif new_state in ["AVAILABLE", "MAINTENANCE"]:
            # If freeing or breaking the spot, explicitly clear the booking data
            update_expr += " REMOVE LicensePlate, BookedUntil"

        table.update_item(
            Key={'LotID': lot_id, 'EntityID': f'SPOT#{sensor_id}'},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

        # 3. Handle METADATA math if MAINTENANCE state changed
        repair_modifier = 0
        if new_state == "MAINTENANCE" and old_state != "MAINTENANCE":
            repair_modifier = 1  # Spot broke
        elif old_state == "MAINTENANCE" and new_state != "MAINTENANCE":
            repair_modifier = -1 # Spot fixed

        if repair_modifier != 0:
            table.update_item(
                Key={'LotID': lot_id, 'EntityID': 'METADATA'},
                UpdateExpression="ADD SpotsUnderRepair :val",
                ExpressionAttributeValues={':val': repair_modifier}
            )

        return make_response(200, {
            "message": f"Successfully updated {sensor_id} to {new_state}",
            "previous_state": old_state
        })

    except json.JSONDecodeError:
        return make_response(400, {"error": "Invalid JSON body payload."})
    except Exception as e:
        print(f"Error updating DynamoDB: {str(e)}")
        return make_response(500, {"error": "Internal server error updating state."})