from agents import function_tool, RunContextWrapper
from handlers.main_handler import _format_transcript,how_long_ago,get_msgs_from_last_states,get_delivery_date, get_package_historic,get_id_package,get_delivery_address,reverse_geocode_osm,send_location_to_whatsapp
import os
import psycopg2
from openai import OpenAI
from psycopg2.extras import Json
from dotenv import load_dotenv

client = OpenAI()

load_dotenv()

admins={
    "50671474099@s.whatsapp.net": "Milagro Fallas",
}

def is_admin(user_id)->bool:
    if admins.get(user_id):
        return True
    else:
        return False

async def resume_memorie_AI(client, transcript: str, lang="es") -> str:
    """
    Genera un resumen de lo hablado por el usuario y el asistente en la interaccion
    """
    sys = (
        "Eres un asistente que resume conversaciones breves entre un usuario y un agente de IA de Moovin. "
        "Devuelve un único resumen claro y conciso en español "
        "Incluye intención/es del usuario, datos concretos (número de guía, teléfono, etc.), "
        "acciones/decisiones del agente, próximos pasos o datos que veas de relevancia en la conversacion. No inventes datos."
    )
    user_msg = (
        "Transcripción (Usuario/Agente):\n"
        "--------------------------------\n"
        f"{transcript}\n"
        "--------------------------------\n"
        "Genera el resumen solicitado."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()

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
        lines.append(f"{fecha} - {estado})")

    return "\n".join(lines)

def retrieve_similar_timelines(embedding: list, top_k: int = 3) -> list:
    """
    Devuelve los 'top_k' timelines más similares como una lista de dicts:
      {
        "package_id": <int|str>,
        "last_status": <str>,
        "date_last_update": <str>,
        "timeline": <str>
      }
    """
    import json as _json
    conn = psycopg2.connect(os.environ["SUPABASE_URL"])
    cur = conn.cursor()
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    cur.execute("""
        SELECT content, metadata
        FROM (
            SELECT content, embedding, metadata
            FROM public.sac_moovin_package_status_kb
            ORDER BY insert_date DESC
            LIMIT 200
        ) AS recent
        ORDER BY embedding <#> %s::vector
        LIMIT %s
    """, (embedding_str, top_k))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    out = []
    for content, metadata in rows:
        if isinstance(metadata, str):
            try:
                metadata = _json.loads(metadata)
            except Exception:
                metadata = {}
        elif metadata is None:
            metadata = {}

        out.append({
            "package_id": metadata.get("package_id"),
            "last_status": metadata.get("last_status"),
            "date_last_update": metadata.get("date_last_update"),
            "timeline": content
        })

    return out

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
    async def get_package_timeline(ctx: RunContextWrapper, package_id: str, phone: str) -> dict:
        """
        Devuelve el historial del paquete solo si el número de teléfono coincide con el del dueño.
        """
        print(f"🔍 Obteniendo timeline del paquete {package_id} para el teléfono {phone}...")
        user_id=ctx.context.user_id
        admin=is_admin(user_id)
        admin and print(f"Admin {admins.get(user_id,"Default Admin")} consultando, Algunas prubeas no seran realizadas")
        
        package_id = await get_id_package(pool, package_id)
        if not package_id:
            return {
                "status": "error", 
                "message": f"Paquete {package_id} no encontrado en la base de datos, estas seguro es este el paquete correcto?",
                "next_step":"Informa al usuario del error inmediatamente y verifica el numero de paquete"
                }
        try:
            historic = await get_package_historic(pool, package_id)
        except Exception as e:
            print(f"🔴 [ERROR] Fallo al obtener el histórico del paquete {package_id}: {e}")
            return {
                    "status":"error",
                    "message":"Hubo un problema al obtener el historial del paquete",
                    "next_step":"Informa al usuario del error inmediatamente"
                    }

        phone_dueño = historic.get("telefono_dueño")
        if not phone_dueño:
            print(f"🔴 [ERROR] Telefono no disponible en la Base de Datos {historic}")
            return {
                    "status":"error",
                    "message": "Paquete no tiene telefono asociado en la Base de datos. en este caso no podre realizar la consulta",
                    "next_step":"Informa al usuario del error inmediatamente"
                    }

        if phone_dueño.strip().lower() != phone.strip().lower() and not admin:
            print(f"🟠 [WARNING] Teléfono no coincide. Proporcionado: {phone}, Dueño: {phone_dueño}")
            return {
                    "status":"error",
                    "message": "El teléfono proporcionado no coincide con el dueño del paquete, podrias verificar el numero correcto",
                    "next_step":"Informa al usuario del error inmediatamente y solicita el dato correcto"
                    }
        
        return {
            "status":"success",
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
        description_override="Obtiene timelines parecidos al del usuario apartir del tracking o numero de seguimiento; devuelve 3 paquetes con su último estado y su timeline."
    )
    async def get_likely_package_timelines(package_id: str) -> dict:
        print(f"🔍 Buscando timelines similares para el paquete {package_id}...")
        package = await get_id_package(pool, enterprise_code=package_id)
        raw_data = await get_package_historic(pool, package)
        timeline_str = convert_timeline_to_text(raw_data["timeline"])
        embedding = get_embedding(timeline_str)

        similar_items = retrieve_similar_timelines(embedding, top_k=3)

        try:
            timeline_array = raw_data["timeline"]
            last_state = timeline_array[-1] if timeline_array else {}
            last_status = last_state.get("status")
            date = last_state.get("dateUser")
            metadata = {
                "package_id": package,
                "last_status": last_status,
                "date_last_update": date
            }
            insert_timeline_to_vectorstore(timeline_str, embedding, metadata)
        except Exception as e:
            print(f"⚠️ No se pudo indexar el timeline base: {e}")

        return {
            "status": "success",
            "package": package_id,
            "similares": similar_items
        }

    return get_likely_package_timelines

# Factory function para enviar la ubicacion de entrega actual del paquete
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
        package = await get_id_package(tools_pool, package)
        user_id=ctx.context.user_id
        admin=is_admin(user_id)
        admin and print(f"Admin {admins.get(user_id,"Default Admin")} consultando, Algunas prubeas no seran realizadas")
        print(f"Location sent es {ctx.context.location_sent}")
        try:
            historic = await get_package_historic(tools_pool, package)
        except Exception as e:
            print(f"🔴 [ERROR] Fallo al obtener el histórico del paquete {package}: {e}")
            return {
                "status":"error",
                "message": "Hubo un problema al obtener el historial del paquete",
                "next_step":"Informa al usuario del error inmediatamente"
                }

        phone_dueño = historic.get("telefono_dueño")
        if not phone_dueño:
            print(f"🔴 [ERROR] No se encontró el teléfono del dueño del paquete en los datos: {historic}")
            return{
                    "status":"error",
                    "message": "No se encontró el teléfono en nuestra Base de datos para el paquete",
                    "next_step":"Informa al usuario del error inmediatamente"
                   }

        if phone_dueño.strip().lower() != phone.strip().lower() and not admin:
            print(f"🟠 [WARNING] Teléfono no coincide. Proporcionado: {phone}, Dueño: {phone_dueño}")
            return{
                    "status":"error",
                    "message":"El teléfono proporcionado no coincide con el dueño del paquete, verifica el numero de telefono y podre volver a intentarlo",
                    "next_step":"Informa al usuario del error inmediatamente y solicita el numero de telefono correcto"
                    }
        
        delivery_address= await get_delivery_address(tools_pool,enterprise_code=package)
        lat=delivery_address.get("latitude",None)
        lng=delivery_address.get("longitude",None)
        try:
            address_response =reverse_geocode_osm(lat, lng)
            address_data=address_response.get("address",{})
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
                        if "confirmations" in ctx.context.location_sent:
                            ctx.context.location_sent["confirmations"]["is_request_confirmed_by_user"] = True
                            print(f"Valor actuailizado del contexto de location")
                        return {
                            "status": "Success",
                            "reason":" Se envio el mensaje al usuario con la ubicacion en formato de Whatsapp",
                            "delivery_address":address,
                            "location_data":{
                                "latitude":lat,
                                "longitude":lng,
                            }
                        }
                    else:
                        return {
                            "status":"error",
                            "message":"Ocurrio un error al enviar la Ubiacion a Whatsapp",
                            "next_step":"Informa al usuario del error inmediatamente"
                        }
            else:
                return {
                    "status":"error",
                    "message":"Ocurrio un error al buscar la direccion de entrega actual",
                    "next_step":"Informa al usuario del error inmediatamente"
                }
        except Exception as e:
            print(f"❌ Error al enviar la direccion al usuario: {e}")
            return {
                "status":"error",
                "message":"Error al enviar la direccion actual del paquete",
                "next_step":"Informa al usuario del error inmediatamente"
                }
        
        
        
    return send_current_delivery_address

# Factory function para funcion que recuerda
def Make_remember_tool(pool):
    from typing import Dict, Any, List
    @function_tool(
        name_override="remember_more",
        description_override="Recupera un resumen de lo hablado en las últimas 3 sesiones (más reciente → más antigua)."
    )
    async def remember(ctx: RunContextWrapper) -> dict:
        print("🧠 Recordando interacciones pasadas con el usuario")
        try:
            if ctx.context.backup_memory_called:
                print(["🧠 Ya recordó esta información"])
                return {
                    "status":"success",
                    "message":"You already remembered this information, and sessions haven't changed"
                }
            last_states = await get_msgs_from_last_states(pool, ctx.context.user_id)
            memories = {}
            for i, state in enumerate(last_states, start=1):
                fecha = state.get("fecha")
                ordered = ((state.get("messages") or {}).get("ordered_msgs") or [])
                transcript = _format_transcript(ordered, max_chars=6000)
                resumen = await resume_memorie_AI(client, transcript)
                memories[f"sesion_{i}"] = {
                    "cuando": how_long_ago(fecha),
                    "fecha": fecha,
                    "resumen": resumen
                }
            ctx.context.backup_memory_called=True
            return memories
        except Exception as e:
            print(f"Error al recuperar/resumir mensajes: {e}")
            return {
                    "status":"error",
                    "message": "No pude generar un resumen de sesiones antiguas",
                    "next_step":"Informa al usuario del error inmediatamente"
                    }
    return remember
