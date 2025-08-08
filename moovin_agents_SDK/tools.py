from agents import function_tool, RunContextWrapper
from database_handler import get_delivery_date, get_package_historic,get_id_package,get_delivery_address,reverse_geocode_osm,send_location_to_whatsapp
import os
import psycopg2
from openai import OpenAI
from psycopg2.extras import Json



client = OpenAI()

# Funciones para Vector Store #
def get_embedding(text: str, model: str = "text-embedding-3-small") -> list:
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding

def convert_timeline_to_text(timeline_data: list) -> str:
    """
    Convierte una lista de estados del paquete (timeline) en un string legible y resumido,
    adecuado para generar embeddings o visualizar.
    """
    lines = []
    for entry in timeline_data:
        fecha = entry.get("dateUser", "Fecha desconocida")
        estado = entry.get("status", "Estado desconocido")
        responsable = entry.get("fullName", "Desconocido")
        lines.append(f"{fecha} - {estado} (por {responsable})")

    return "\n".join(lines)

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
            "timeline": historic.get("timeline","Dato no fue encontrado"),
            "Numero de Telefono": phone_dueño,
            "Dueño del Paquete": historic.get("nombre_dueño_paquete","Dato no fue encontrado"),
            "Tienda donde se compro el paquete":historic.get("tienda_donde_se_compro","Dato no fue encontrado")
        }

    return get_package_timeline


# Factory function for get_likely_package_timelines tool
def make_get_likely_package_timelines_tool(pool):
    @function_tool(
    name_override="get_likely_package_timelines",
    description_override="Obtiene timelines parecidos al del usuario apartir del tracking o numero de seguimiento, usala para obtener contexto unicamente." 
    )
    async def get_likely_package_timelines(package_id: str) -> str:
        print(f"🔍 Buscando timelines similares para el paquete {package_id}...")
        package= await get_id_package(pool, enterprise_code=package_id)
        raw_data = await get_package_historic(pool, package)
        timeline_str = convert_timeline_to_text(raw_data["timeline"])
        embedding = get_embedding(timeline_str)
        similar_timelines = retrieve_similar_timelines(embedding, top_k=5)

        timeline_array=raw_data["timeline"]        
        last_state = timeline_array[len(timeline_array) - 1]
        last_status = last_state["status"]
        date=last_state["dateUser"]
        metadata = {
            "package_id": package,
            "last_status":last_status,
            "date_last_update":date
            }
        insert_timeline_to_vectorstore(timeline_str, embedding, metadata)

        response = (
            f"Timeline del paquete {package_id}"
            f"Timelines similares encontrados:\n- " + "\n- ".join(similar_timelines)
        )

        return response

    return get_likely_package_timelines

def Make_send_current_delivery_address_tool(tools_pool):
    @function_tool(
    name_override="send_current_delivery_address",
    description_override="Envia al usuario la direccion de entrega actual para el paquete, numero de seguimiento y numero de telefono del paquete son necesarios." 
    )
    async def send_current_delivery_address(
        ctx: RunContextWrapper,
        package:str,
        phone: str
    ) -> dict:
        print (f"🌎 Buscando la direcion de entrega para el paquete {package} con telefono {phone}")
        try:
            historic = await get_package_historic(tools_pool, package)
        except Exception as e:
            print(f"🔴 [ERROR] Fallo al obtener el histórico del paquete {package}: {e}")
            return {"error": "Hubo un problema al obtener el historial del paquete."}

        phone_dueño = historic.get("telefono_dueño")
        if not phone_dueño:
            print(f"🔴 [ERROR] No se encontró el teléfono del dueño del paquete en los datos: {historic}")
            return {"error": "No se encontró el teléfono del dueño del paquete."}

        if phone_dueño.strip().lower() != phone.strip().lower():
            print(f"🟠 [WARNING] Teléfono no coincide. Proporcionado: {phone}, Dueño: {phone_dueño}")
            return {"error": "El teléfono proporcionado no coincide con el dueño del paquete."}
        
        delivery_address= await get_delivery_address(tools_pool,enterprise_code=package)
        lat=delivery_address.get("latitude",None)
        lng=delivery_address.get("longitude",None)
        try:
            address_response =reverse_geocode_osm(lat, lng)
            address_data=address_response.get("address",{})
            user_id=ctx.context.user_id
            if address_data:
                town_name=address_data.get("road") or address_data.get("county") or None
                if not town_name:
                    print (f"Falta el nombre del pueblo")
                full_address=address_response.get("display_name", None)
                if town_name and full_address:
                    is_message_sent=await send_location_to_whatsapp(user_id,lat,lng,town_name,full_address)
                    message_sent_data=is_message_sent.json()
                    message=message_sent_data.get("message", None)
                    location_data=message.get("locationMessage",None)
                    if location_data:
                        address=location_data.get("address")
                        return {
                            "status": "Success, message with ubication in ubication format was sent to user",
                            "delivery_address":address
                        }
                    else:
                        return {
                            "status":"error",
                            "reason":"error ocurred while sending the ubication through whatsapp"
                        }
            else:
                return {
                    "status","error",
                    "reason","an error ocurred while finding the address name"
                }
        except Exception as e:
            print(f"❌ Error al enviar la direccion al usuario: {e}")
            return "[Error al enviar direccion al usuario]"
        
        
        
    return send_current_delivery_address
