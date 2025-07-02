from langchain.tools import tool
import os
import locale
from datetime import datetime
import openai
import json
import psycopg2
import tiktoken
from psycopg2.extras import Json
from mcp.AI_router import run_mcp
from app.database_handler import get_id_package, get_delivery_date, get_package_timeline

openai.api_key = os.environ.get("OPEN_AI_API")

# Español
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

# -------------------- Funciones auxiliares -------------------- #
def format_fecha(date_server):
    fecha_dt = datetime.strptime(str(date_server), "%Y-%m-%d %H:%M:%S")
    return fecha_dt.strftime("%A %d de %B %Y %H:%M")

def get_embedding(text: str, model: str = "text-embedding-3-small") -> list:
    response = openai.embeddings.create(input=text, model=model)
    return response.data[0].embedding

def retrieve_similar_timelines(embedding: list, top_k: int = 5) -> list:
    conn = psycopg2.connect(os.environ["SUPABASE_URL"])
    cur = conn.cursor()
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    cur.execute("""
        SELECT content
        FROM (
            SELECT content, embedding
            FROM public.sac_moovin_package_status_kb
            ORDER BY insert_date DESC
            LIMIT 30
        ) AS recent
        ORDER BY embedding <#> %s::vector
        LIMIT %s
    """, (embedding_str, top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row[0] for row in rows]

def insert_timeline_to_vectorstore(content: str, embedding: list, metadata: dict):
    conn = psycopg2.connect(os.environ["SUPABASE_URL"])
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sac_moovin_package_status_kb (content, embedding, metadata)
        VALUES (%s, %s, %s)
    """, (content, embedding, Json(metadata)))
    conn.commit()
    cur.close()
    conn.close()

def TracerAI(context_data: dict, model: str = "gpt-4o") -> str:
    """
   LLM Que genera interpretacion "humana" del paquete.
    """
    with open("app/prompt_TracerAI.txt", "r", encoding="utf-8") as f:
        base_system_prompt = f.read()

    if not context_data.get("found", False) or not context_data.get("estados"):
        return context_data.get("message", "No hay información para interpretar.")

    timeline_str = json.dumps(context_data["estados"], indent=2, ensure_ascii=False)
    embedding = get_embedding(timeline_str)
    similares = retrieve_similar_timelines(embedding)

    similares_str = "\n\n--- Ejemplo similar ---\n" + "\n\n--- Ejemplo similar ---\n".join(similares) if similares else "No se encontraron ejemplos similares."

    system_prompt = (
        f"{base_system_prompt}\n\n"
        f"Ejemplos similares de paquetes para contexto del agente:\n{similares_str}"
    )

    prompt = f"Aquí tienes el historial del paquete:\n{timeline_str}"

    print(f"[TracerAI][DEBUG] Similares traidos desde KB {similares_str}")
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        respuesta = response.choices[0].message.content
    except Exception as e:
        print(f"[TracerAI][ERROR] Fallo la llamada a OpenAI: {e}")
        return "Error interno: no se pudo obtener la interpretación del historial."

    metadata = {
        "enterprise_code": context_data.get("enterprise_code"),
        "status_final": context_data["estados"][-1].get("status") if context_data["estados"] else "DESCONOCIDO"
    }
    insert_timeline_to_vectorstore(timeline_str, embedding, metadata)
    return respuesta

# ------------------ Tools ------------------ #
def make_get_package_context_tool(pool):
    @tool(description="Obtiene el contexto de un paquete dado su enterpriseCode.")
    async def get_package_context(enterprise_code: str) -> str:
        id_package = await get_id_package(pool, enterprise_code)
        if not id_package:
            return {
                "enterprise_code": enterprise_code,
                "found": False,
                "message": f"No se encontró ningún paquete con enterpriseCode {enterprise_code}.",
                "estados": []
            }
        timeline = await get_package_timeline(pool, id_package)
        context = {
            "enterprise_code": enterprise_code,
            "found": True,
            "estados": timeline if timeline else []
        }
        trace_result = TracerAI(context)
        return trace_result
    return get_package_context

def make_get_SLA_tool(pool):
    @tool(description="Obtiene la fecha de entrega de un paquete dado su enterpriseCode.")
    async def get_SLA(enterprise_code: str) -> dict:
        response = await get_delivery_date(pool, enterprise_code)
        return response
    return get_SLA

@tool(description="Agente AI que ejecuta acciones en el MCP. Usalo para crear tickets, notificar humanos, debe ser un string con la informacion del usuario para el ticket")
async def run_mcp_action(instruccion: str) -> str:
    return run_mcp(instruccion)
