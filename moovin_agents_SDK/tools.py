from agents import function_tool
from database_handler import get_delivery_date, get_package_historic,get_id_package
import os
import psycopg2
from openai import OpenAI
from psycopg2.extras import Json


client = OpenAI()

# Funciones para Vector Store #
def get_embedding(text: str, model: str = "text-embedding-3-small") -> list:
    response = client.embeddings.create(input=text, model=model)
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

# Factory function for get_SLA tool
def make_get_SLA_tool(pool):
    @function_tool(
        name_override="get_SLA",
        description_override="Obtiene la fecha estimada de entrega de un paquete a partir de su Tracking o numero de segumiento."
    )
    async def get_SLA(enterprise_code: str) -> dict:
        print(f"🔍 Obteniendo SLA del paquete {enterprise_code}...")
        return await get_delivery_date(pool, enterprise_code)

    return get_SLA

# Factory function for get_package_timeline tool
def make_get_package_timeline_tool(pool):
    @function_tool(
        name_override="get_package_timeline",
        description_override="Obtiene el historico del paquete del usuario a partir de su Tracking o número de seguimiento y su número de teléfono."
    )
    async def get_package_timeline(package_id: str, phone: str) -> dict:
        """
        Devuelve el historial del paquete solo si el número de teléfono coincide con el del dueño.
        """
        print(f"🔍 Obteniendo timeline del paquete {package_id} para el teléfono {phone}...")

        try:
            historic = await get_package_historic(pool, package_id)
        except Exception as e:
            print(f"🔴 [ERROR] Fallo al obtener el histórico del paquete {package_id}: {e}")
            return {"error": "Hubo un problema al obtener el historial del paquete."}

        phone_dueño = historic.get("telefono_dueño")
        if not phone_dueño:
            print(f"🔴 [ERROR] No se encontró el teléfono del dueño del paquete en los datos: {historic}")
            return {"error": "No se encontró el teléfono del dueño del paquete."}

        if phone_dueño.strip().lower() != phone.strip().lower():
            print(f"🟠 [WARNING] Teléfono no coincide. Proporcionado: {phone}, Dueño: {phone_dueño}")
            return {"error": "El teléfono proporcionado no coincide con el dueño del paquete."}
        return {
            "timeline": historic.get("timeline"),
            "Numero de Telefono": phone_dueño
        }

    return get_package_timeline


@function_tool(
    name_override="get_likely_package_timelines",
    description_override="Obtiene timelines parecidos al del usuario, usala para obtener contexto unicamente."
)
async def get_likely_package_timelines(package_id: str) -> str:
    print(f"🔍 Buscando timelines similares para el paquete {package_id}...")
    package=get_id_package(package_id)
    timeline = await get_package_historic( package)

    embedding = get_embedding(timeline)

    similar_timelines = retrieve_similar_timelines(embedding, top_k=5)

    metadata = {"package_id": package}
    insert_timeline_to_vectorstore(timeline, embedding, metadata)

    response = (
        f"Timeline del paquete {package_id} del usuario:\n{timeline}\n\n"
        f"Timelines similares encontrados:\n- " + "\n- ".join(similar_timelines)
    )

    return response