import boto3
import time
import json
import os
import re
from botocore.exceptions import ClientError
from pydantic_ai import Agent

athena = boto3.client("athena")

# Configuración de entorno
DATABASE = "iot_data"
TABLE = "gold_bucket_ccc_iot_2026"  # Ensure this matches your Crawler output
OUTPUT = "s3://temporal-athena-ccc-iot-2026/athena-results/"

# -----------------------------
# Secrets
# -----------------------------
def get_secret():
    secret_name = "LLM_API"
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    resp = client.get_secret_value(SecretId=secret_name)
    secret_string = resp["SecretString"]

    try:
        secret_data = json.loads(secret_string)
        actual_api_key = list(secret_data.values())[0]
    except (json.JSONDecodeError, AttributeError, IndexError):
        actual_api_key = secret_string

    os.environ["PYDANTIC_AI_GATEWAY_API_KEY"] = actual_api_key.strip()

def ask_llm(prompt: str) -> str:
    agent = Agent("gateway/bedrock:amazon.nova-micro-v1:0")
    result = agent.run_sync(prompt)
    return result.output

# -----------------------------
# Ejecución en Athena
# -----------------------------
def run_athena_query(query: str):
    resp = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": OUTPUT}
    )
    qid = resp["QueryExecutionId"]
    
    # Poll de estado con protección de Timeout
    max_retries = 15  # Máximo 15 segundos esperando a Athena
    attempts = 0
    state = "QUEUED"
    
    while attempts < max_retries:
        status = athena.get_query_execution(QueryExecutionId=qid)
        state = status["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.5)
        attempts += 1

    if state != "SUCCEEDED":
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown reason")
        raise RuntimeError(f"Athena falló o tardó demasiado: {state} - {reason}")

    results = athena.get_query_results(QueryExecutionId=qid)
    rows = results["ResultSet"]["Rows"]
    
    if not rows: 
        return {"columns": [], "rows": []}
    
    header = [c.get("VarCharValue", "") for c in rows[0]["Data"]]
    data_rows = []
    for r in rows[1:]:
        values = [d.get("VarCharValue") for d in r.get("Data", [])]
        data_rows.append(dict(zip(header, values)))

    return {"columns": header, "rows": data_rows}

# -----------------------------
# Filtros Directos (Para Dashboards)
# -----------------------------
_SAFE_ID = re.compile(r"^[a-zA-Z0-9_\-:.]+$")
_SAFE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def build_filtered_query(device_id: str | None, date: str | None, limit: int) -> str:
    where = []

    if device_id:
        if not _SAFE_ID.match(device_id):
            raise ValueError("Formato de device_id inválido")
        where.append(f"device_id = '{device_id}'")

    if date:
        if not _SAFE_DATE.match(date):
            raise ValueError("Formato de fecha inválido (se espera YYYY-MM-DD)")
        where.append(f"event_date = '{date}'")

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    
    # Ordenamos por timestamp descendente para ver lo más reciente primero
    return f"""
SELECT *
FROM {DATABASE}.{TABLE}
{where_clause}
ORDER BY event_timestamp DESC
LIMIT {limit}
""".strip()

def build_latest_status_query(device_id: str | None) -> str:
    """Returns the latest status per sensor, ordered by sensor_id."""
    outer_where = ["rn = 1"]

    if device_id:
        if not _SAFE_ID.match(device_id):
            raise ValueError("Formato de device_id inválido")
        outer_where.append(f"device_id = '{device_id}'")

    where_clause = "WHERE " + " AND ".join(outer_where)

    return f"""
SELECT * FROM (
    SELECT *, row_number() OVER (PARTITION BY sensor_id ORDER BY event_timestamp DESC) as rn
    FROM {DATABASE}.{TABLE}
)
{where_clause}
ORDER BY sensor_id ASC
""".strip()

# -----------------------------
# Auxiliar para CORS
# -----------------------------
def make_response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST"
        },
        "body": json.dumps(body_dict)
    }

# -----------------------------
# HANDLER PRINCIPAL (Enrutador)
# -----------------------------
def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {"ok": True})

    params = event.get("queryStringParameters") or {}
    
    # Por defecto usaremos el modo LLM si no se especifica
    mode = params.get("mode", "llm").lower()
    print("Modo seleccionado:", mode)

    # ==========================================
    # MODO 1: FILTROS DIRECTOS (Dashboards/Diagramas)
    # ==========================================
    if mode == "filters":
        device_id = params.get("device_id")
        date = params.get("date")
        latest = params.get("latest", "false").lower() == "true"
        limit_raw = params.get("limit", "100")

        try:
            limit = int(limit_raw)
            limit = max(1, min(limit, 1000))
        except ValueError:
            return make_response(400, {"error": "El límite (limit) debe ser un número entero"})

        try:
            if latest:
                query = build_latest_status_query(device_id=device_id)
            else:
                query = build_filtered_query(device_id=device_id, date=date, limit=limit)
            result = run_athena_query(query)
            return make_response(200, {
                "mode": "filters", 
                "query": query, 
                "result": result
            })
        except Exception as e:
            return make_response(500, {"error": str(e)})

    # ==========================================
    # MODO 2: ASISTENTE RAG (LLM)
    # ==========================================
    elif mode == "llm":
        user_prompt = params.get("prompt")
        
        if not user_prompt:
            return make_response(400, {"error": "Falta el parámetro 'prompt' para el modo LLM"})

        try:
            get_secret()
            
            # STEP 1: Generate the SQL Query
            sql_gen_prompt = f"""
            Generate a SQL query for AWS Athena (Presto SQL).
            Table: `{DATABASE}.{TABLE}`
            
            DATA MODEL:
            - device_id (string): Identifier of the entire PARKING LOT (zone/lot).
            - sensor_id (string): Identifier of an INDIVIDUAL PARKING SPOT within the lot.
            - status (string): Current state of the individual spot ('OCCUPIED' or 'FREE').
            - event_timestamp (string): Timestamp of the status change event.
            - event_date (string): Date of the event (YYYY-MM-DD).
            - event_time (string): Time of the event (HH:MM:SS).
            - lot_usable_spaces (int): Total number of OPERATIONAL spots in the parking lot (excludes reserved/maintenance). This is a lot-level field, not per-spot.
            - lot_physical_capacity (int): Total physical capacity of the parking lot (includes reserved/maintenance). This is a lot-level field, not per-spot.

            IMPORTANT CONTEXT:
            - The table stores status change EVENTS. Each row is a status change for a single spot.
            - Spots do not change status at the same frequency: one spot may have many more records than another.
            - To get the CURRENT state of each spot, you must keep only the most recent event per sensor_id.
            - The number of operational spots in a lot equals lot_usable_spaces. The rest are out of service.
            - CRITICAL: lot_physical_capacity and lot_usable_spaces are LOT-LEVEL CONSTANTS repeated identically on every row. NEVER use SUM/COUNT on them. To read their value, simply select them from any single row (e.g., SELECT lot_physical_capacity, lot_usable_spaces FROM table LIMIT 1).

            EXAMPLES:
            - "How many spots does the parking have?" → SELECT lot_physical_capacity, lot_usable_spaces FROM {DATABASE}.{TABLE} LIMIT 1
            - "Which spots are free right now?" / "Where can I park?" → SELECT device_id, sensor_id, status, event_timestamp FROM (SELECT *, row_number() OVER (PARTITION BY sensor_id ORDER BY event_timestamp DESC) as rn FROM {DATABASE}.{TABLE}) WHERE rn = 1 AND status = 'FREE' ORDER BY sensor_id ASC
            - "Which spots are occupied?" → SELECT device_id, sensor_id, status, event_timestamp FROM (SELECT *, row_number() OVER (PARTITION BY sensor_id ORDER BY event_timestamp DESC) as rn FROM {DATABASE}.{TABLE}) WHERE rn = 1 AND status = 'OCCUPIED' ORDER BY sensor_id ASC
            - "How many cars are parked?" → SELECT COUNT(*) as parked_cars FROM (SELECT *, row_number() OVER (PARTITION BY sensor_id ORDER BY event_timestamp DESC) as rn FROM {DATABASE}.{TABLE}) WHERE rn = 1 AND status = 'OCCUPIED'
            - "What is the status of all spots?" → SELECT device_id, sensor_id, status, event_timestamp FROM (SELECT *, row_number() OVER (PARTITION BY sensor_id ORDER BY event_timestamp DESC) as rn FROM {DATABASE}.{TABLE}) WHERE rn = 1 ORDER BY sensor_id ASC

            User question: "{user_prompt}"
            
            RULES: 
            1. Return ONLY the SQL code with no markdown formatting or additional text.
            2. If the user asks for the current state of spots, use the row_number pattern shown in the examples.
            3. Only include lot_physical_capacity or lot_usable_spaces in the SELECT if the user explicitly asks about capacity or total spots. Otherwise select only: device_id, sensor_id, status, event_timestamp.
            4. If the user's question is NOT related to the parking system (spots, availability, capacity, status, parking), return ONLY the text: NOT_PARKING_RELATED
            """
            
            raw_sql_query = ask_llm(sql_gen_prompt)
            sql_query = raw_sql_query.replace("```sql", "").replace("```", "").strip()

            # Check if the LLM flagged the question as off-topic
            if "NOT_PARKING_RELATED" in sql_query.upper():
                return make_response(200, {
                    "output": "Lo siento, solo puedo ayudarte con preguntas sobre el parking: plazas libres, ocupadas, capacidad, etc. ¿En qué puedo ayudarte?",
                    "sql": None,
                    "result": {"columns": [], "rows": []}
                })
            
            if "SELECT" not in sql_query.upper():
                 return make_response(400, {"error": "El LLM no pudo generar una query válida", "debug": sql_query})

            # PASO 2: Ejecutar en Athena
            athena_results = run_athena_query(sql_query)

            # STEP 3: Generate final response (RAG)
            rag_prompt = f"""
            You are the intelligent assistant of an IoT-sensor-based parking system.
            The user asked: "{user_prompt}"
            
            DATA MODEL:
            - device_id = identifier of the entire PARKING LOT (zone/lot).
            - sensor_id = identifier of an INDIVIDUAL PARKING SPOT within the lot.
            - status = current state of that spot: 'OCCUPIED' or 'FREE'.
            - lot_usable_spaces = total operational (usable) spots in the lot (excludes maintenance/reserved).
            - lot_physical_capacity = total physical capacity of the lot (includes spots under maintenance).
            - The data consists of status change events. If filtered with row_number, each row represents the most recent state of each spot.

            Real sensor data:
            {json.dumps(athena_results['rows'])}

            Instructions:
            - The data above is COMPLETE and RELIABLE. It comes directly from real-time sensors. Trust it fully.
            - CRITICAL: NEVER invent, fabricate, or assume data that is NOT present above. Only describe spots that explicitly appear in the data. If a spot is not in the data, do NOT mention it.
            - NEVER say you don't have information or that data is missing. The data above IS the answer.
            - Only answer what the user asked. If they ask where to park, ONLY list free spots. If they ask which are occupied, ONLY list occupied spots. Do NOT list both unless explicitly asked for the full status.
            - If the query returned lot_physical_capacity and lot_usable_spaces, state those numbers confidently (e.g., "The parking has 14 total spots, of which 12 are currently usable").
            - If the query returned individual spots, describe them clearly with their spot IDs.
            - When listing spots, sort them in NUMERICAL ORDER (spot-01, spot-02, spot-03, ...).
            - Only mention lot_physical_capacity or lot_usable_spaces if the user EXPLICITLY asks about capacity, total spots, or how many spots exist. If the user asks about free/occupied spots, parking availability, or where to park, do NOT mention capacity numbers even if they appear in the data.
            - If the data is empty or does not seem to match the question, ask the user to rephrase or be more specific. Do NOT say "I don't know".
            - Do NOT mention databases, JSON, queries, or sensors.
            - You may use markdown formatting (bold, lists, etc.) to make the answer clearer.
            - IMPORTANT: Reply in the SAME LANGUAGE as the user's question. Detect the language of the question and respond accordingly.
            """
            
            final_response = ask_llm(rag_prompt)

            return make_response(200, {
                "output": final_response,
                "sql": sql_query,
                "result": athena_results
            })

        except Exception as e:
            return make_response(500, {"error": str(e)})
            
    # ==========================================
    # MODO DESCONOCIDO
    # ==========================================
    else:
        return make_response(400, {"error": f"Modo '{mode}' desconocido. Usa 'llm' o 'filters'."})