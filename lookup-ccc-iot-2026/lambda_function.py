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
        time.sleep(1)
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
        limit_raw = params.get("limit", "100")

        try:
            limit = int(limit_raw)
            limit = max(1, min(limit, 1000))
        except ValueError:
            return make_response(400, {"error": "El límite (limit) debe ser un número entero"})

        try:
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
            
            # PASO 1: Generar la Query SQL
            sql_gen_prompt = f"""
            Genera una consulta SQL para AWS Athena (Presto SQL).
            Tabla: `{DATABASE}.{TABLE}`
            Columnas:
            - device_id (string): ID del dispositivo/parking o zona.
            - sensor_id (string): ID del sensor específico o plaza.
            - status (string): Estado (ej: 'OCCUPIED', 'FREE').
            - event_timestamp (string): Marca de tiempo completa.
            - event_date (string): Fecha del evento (YYYY-MM-DD).
            - event_time (string): Hora del evento (HH:MM:SS).
            - lot_available_spaces (int): Espacios libres totales en el lote.
            - lot_physical_capacity (int): Capacidad total del lote.

            Pregunta usuario: "{user_prompt}"
            
            REGLAS: 
            1. Devuelve SOLO el código SQL sin formato markdown ni texto adicional.
            2. Si pide el estado actual de las plazas, usa EXACTAMENTE esta query base y añade los filtros necesarios: 
               SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY sensor_id ORDER BY event_timestamp DESC) as rn FROM {DATABASE}.{TABLE}) WHERE rn = 1
            """
            
            raw_sql_query = ask_llm(sql_gen_prompt)
            sql_query = raw_sql_query.replace("```sql", "").replace("```", "").strip()
            
            if "SELECT" not in sql_query.upper():
                 return make_response(400, {"error": "El LLM no pudo generar una query válida", "debug": sql_query})

            # PASO 2: Ejecutar en Athena
            athena_results = run_athena_query(sql_query)

            # PASO 3: Generar respuesta final (RAG)
            rag_prompt = f"""
            Eres el asistente inteligente de un parking. 
            El usuario ha preguntado: "{user_prompt}"
            Los datos reales de los sensores en la base de datos son:
            {json.dumps(athena_results['rows'])}

            Instrucciones:
            - Basándote EXCLUSIVAMENTE en estos datos, responde al usuario de forma natural y servicial.
            - Si hay sitios libres, indica la zona y el ID de la plaza.
            - Si no hay datos relevantes, dilo amablemente.
            - No uses markdown ni menciones que estás leyendo una base de datos o JSON.
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