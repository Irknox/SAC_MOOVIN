import aiomysql
from datetime import datetime
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
from pydantic import BaseModel
import re
import phonenumbers
import base64
import requests
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo 


# ----------------- Configuración de MySQL ------------------
load_dotenv()
TOOLS_DB_HOST = os.environ.get('Main_Db_Host')
TOOLS_DB_USER = os.environ.get('Main_Db_User')
TOOLS_DB_PASSWORD = os.environ.get('Main_Db_password')
TOOLS_DB_NAME = os.environ.get('Main_Db')
TOOLS_DB_PORT = int(os.environ.get('Main_Db_Port'))
DB_HOST = os.environ.get('Db_HOST')
DB_USER = os.environ.get('Db_USER')
DB_PASSWORD = os.environ.get('Db_PASSWORD')
DB_NAME = os.environ.get('Db_NAME')
DB_PORT = int(os.environ.get('Db_PORT'))

#--------------------Funciones auxiliares--------------------#
def _format_transcript(ordered_msgs, max_chars=4000) -> str:
    """Convierte ordered_msgs [{role,text}] en un transcript 'Usuario:/Agente:' y recorta si se pasa."""
    lines = []
    role_map = {"user": "Usuario", "assistant": "Agente"}
    for m in ordered_msgs:
        r = role_map.get(m.get("role"), m.get("role","")).strip() or "Otro"
        t = (m.get("text") or "").strip()
        if not t: 
            continue
        lines.append(f"{r}: {t}")
    txt = "\n".join(lines)
    return txt[-max_chars:]

CR_TZ = ZoneInfo("America/Costa_Rica")

def _to_datetime(fecha):
    """Convierte `fecha` (str|datetime) a datetime."""
    if isinstance(fecha, datetime):
        return fecha
    if isinstance(fecha, str):
        s = fecha.strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
    return None

def how_long_ago(fecha, now=None) -> str:
    """Devuelve 'Hace X ...' en español (seg, min, horas, días, semanas, meses, años)."""
    dt = _to_datetime(fecha)
    if dt is None:
        return "Hace un tiempo"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CR_TZ)
    if now is None:
        now = datetime.now(CR_TZ)
        
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0

    if seconds < 60:
        return "Hace unos segundos"
    minutes = seconds // 60
    if minutes < 60:
        return f"Hace {minutes} minuto{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 24:
        return f"Hace {hours} hora{'s' if hours != 1 else ''}"
    days = hours // 24
    if days < 7:
        return f"Hace {days} día{'s' if days != 1 else ''}"
    weeks = days // 7
    if weeks < 5:
        return f"Hace {weeks} semana{'s' if weeks != 1 else ''}"
    months = days // 30
    if months < 12:
        return f"Hace {months} mes{'es' if months != 1 else ''}"
    years = days // 365
    return f"Hace {years} año{'s' if years != 1 else ''}"

async def get_last_states(pool, user_id: str, k: int = 3) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT id, fecha, contexto
                FROM sac_agent_memory
                WHERE user_id = %s
                ORDER BY id DESC     -- más reciente primero
                LIMIT %s
            """, (user_id, k))
            rows = await cur.fetchall()

    result = []
    for r in rows:
        ctx_val = r.get("contexto")
        # normaliza a dict (maneja str/bytes y doble-JSON)
        if isinstance(ctx_val, (bytes, bytearray)):
            try: ctx_val = ctx_val.decode("utf-8")
            except: ctx_val = str(ctx_val)
        if isinstance(ctx_val, str):
            try:
                tmp = json.loads(ctx_val)
                ctx_val = json.loads(tmp) if isinstance(tmp, str) else tmp
            except: 
                ctx_val = {}
        elif not isinstance(ctx_val, dict):
            ctx_val = {}
        result.append({"id": r["id"], "fecha": r["fecha"], "contexto": ctx_val})
    return result

def _normalize_contexto(val: Any) -> Dict:
    """
    Devuelve un dict a partir de un valor que puede venir como:
    - dict
    - str con JSON
    - str con JSON-encadenado (JSON dentro de otro JSON)
    - bytes
    Si no se puede, devuelve {}.
    """
    # bytes -> str
    if isinstance(val, (bytes, bytearray)):
        try:
            val = val.decode("utf-8")
        except Exception:
            val = str(val)

    obj = val
    for _ in range(2):
        if isinstance(obj, str):
            s = obj.strip()
            try:
                obj = json.loads(s)
                continue
            except Exception:
                break
        break

    return obj if isinstance(obj, dict) else {}

def extract_user_and_assistant_messages(
    input_items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Extrae mensajes de 'user' y 'assistant'.
    - input_items: lista con items que tienen 'role' y 'content'
    - keep_order=True: además de listas separadas, devuelve 'ordered' con el flujo en orden

    Devuelve:
    {
      "user": [ ... ],            # solo textos del usuario
      "assistant": [ ... ],       # solo textos del asistente
      "ordered": [                # opcional si keep_order=True
         {"role":"user","text":"..."},
         {"role":"assistant","text":"..."},
         ...
      ]
    }
    """

    def _pull_text(content: Any) -> Optional[str]:
        # Soporta:
        #  - "content": "Hola"
        #  - "content": [{"type":"output_text","text":"{\"response\":\"...\"}"}]
        #  - "content": [{"type":"text","text":"..."}]
        if isinstance(content, str):
            t = content.strip()
            return t or None

        if isinstance(content, list):
            # toma el último bloque con 'text' (suele ser la respuesta final)
            for block in reversed(content):
                text = block.get("text")
                if not isinstance(text, str):
                    continue
                t = text.strip()
                if not t:
                    continue
                # Algunos outputs vienen como JSON con {"response":"..."}
                try:
                    parsed = json.loads(t)
                    if isinstance(parsed, dict) and isinstance(parsed.get("response"), str):
                        return parsed["response"].strip() or None
                except Exception:
                    pass
                return t
        return None

    ordered: List[Dict[str, str]] = []

    for it in (input_items or []):
        role = it.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _pull_text(it.get("content"))
        if not text:
            continue
        ordered.append({"role": role, "text": text})

    result: Dict[str, Any] = {"ordered_msgs": ordered}
    return result

async def get_msgs_from_last_states(pool, user_id: str, states: int = 3) -> List[Dict[str, Any]]:
    """
    Trae los k estados anteriores al último para 'user_id',
    y devuelve una lista con los mensajes relevantes por estado:
    [
      {
        "state_id": 123,
        "fecha": "2025-08-12 11:22:33",
        "messages": [ {"role":"user","text":"..."}, {"role":"assistant","text":"..."} ]
      },
      ...
    ]
    """
    prev_states = await get_last_states(pool, user_id, states)
    grouped: List[Dict[str, Any]] = []
    for s in prev_states:
        ctx = s["contexto"] or {}
        ctx_dict = _normalize_contexto(ctx)
        input_items = ctx_dict.get("input_items") or []
        msgs = extract_user_and_assistant_messages(input_items)
        fecha_val = s["fecha"]
        if hasattr(fecha_val, "strftime"):
            fecha_val = fecha_val.strftime("%Y-%m-%d %H:%M:%S")
        grouped.append({
            "state_id": s["id"],
            "fecha": fecha_val,
            "messages": msgs
        })
    return grouped

def reverse_geocode_osm(lat: float, lon: float) -> str:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "format": "json",
        "lat": lat,
        "lon": lon,
        "zoom": 16,
        "addressdetails": 1
    }
    headers = {
        "User-Agent": "MoovinBot/1.0 alejca15@gmail.com"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return f"[Error OSM {response.status_code}]"
    except Exception as e:
        print(f"❌ Error en reverse_geocode_osm_sync: {e}")
        return "[Error al obtener dirección]"
    
async def send_location_to_whatsapp(user_id: str, latitude: float, longitude: float, name:str, address=str):
    """
    Envía una ubicación por WhatsApp mediante Evolution API.
    """
    url = f"{os.environ.get('Whatsapp_URL')}/message/sendLocation/SAC-Moovin"
    payload = {
        "number": user_id.replace("@s.whatsapp.net", ""),
        "name": name,
        "address": address,
        "latitude": latitude,
        "longitude": longitude
    }


    headers = {
        "apikey": os.environ.get("Whatsapp_API_KEY"),
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        print("📍 Ubicación enviada a WhatsApp ✔️")
        return response
    except Exception as e:
        print("❌ Error al enviar ubicación a WhatsApp:", e)
        return None

def format_fecha(date_server):
    fecha_dt = datetime.strptime(str(date_server), "%Y-%m-%d %H:%M:%S")
    return fecha_dt.strftime("%A %d de %B %Y %H:%M")

async def get_id_package(pool, enterprise_code):
    """
    Intenta primero buscar idPackage usando el valor como un ID (int),
    si falla, entonces busca por enterpriseCode (str).
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                package_id = int(enterprise_code)
                await cur.execute("""
                    SELECT idPackage 
                    FROM package 
                    WHERE idPackage = %s
                    LIMIT 1
                """, (package_id,))
                result = await cur.fetchone()
                if result:
                    return result[0]
            except ValueError:
                print(f"[get_id_package] No es un ID válido, intentando por enterpriseCode")

            await cur.execute("""
                SELECT idPackage 
                FROM package 
                WHERE enterpriseCode = %s
                LIMIT 1
            """, (enterprise_code,))
            result = await cur.fetchone()
            if result:
                print(f"[get_id_package] Encontrado por enterpriseCode: {result[0]}")
            else:
                print("[get_id_package] No encontrado en ninguna forma")
            return result[0] if result else None

async def is_gam(pool, package):
    """
    Retorna True si el paquete tiene un point asociado con gam = 1, sino False.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT point.gam
                FROM package
                JOIN point ON package.fkIdPoint = point.idPoint
                WHERE package.idPackage = %s
            """, (package,))
            result = await cur.fetchone()
            return result is not None and result[0] == 1

async def when__last_in_moovin(pool, package):
    """
    Retorna la ultima fecha de ingreso a una sede Moovin o False
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT dateServer
                FROM packageStatusDetailed
                WHERE fkIdPackageStatus = 3 and idPackage = %s
                order by dateServer desc
                LIMIT 1
            """, (package,))
            result = await cur.fetchone()
            return result[0] if result else False

async def when_received_in_moovin(pool, package):
    """
    Retorna la primera fecha de ingreso a una sede Moovin o False
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT dateServer
                FROM packageStatusDetailed
                WHERE fkIdPackageStatus = 3 and idPackage = %s
                order by dateServer asc
                LIMIT 1
            """, (package,))
            result = await cur.fetchone()
            return result[0] if result else False

async def get_delivery_address(pool, enterprise_code):
    package = await get_id_package(pool, enterprise_code)
    if not package:
        return "No se encontró el paquete."
    else:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT  point.idPoint, point.address, point.province, point.canton, point.district, point.latitude, point.longitude
                    FROM package
                    JOIN point ON package.fkIdPoint = point.idPoint
                    WHERE package.idPackage = %s
                """, (package,))
                delivery_address = await cur.fetchone()
                if not delivery_address:
                    return "No se encontró la dirección de entrega."
                return delivery_address

async def get_package_historic(pool, package_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT 
                    PSD.dateUser,
                    (
                        SELECT name
                        FROM packageStatus
                        WHERE idPackageStatus = PSD.fkIdPackageStatus
                    ) AS status,
                    U.idUser
                FROM packageStatusDetailed PSD
                INNER JOIN user U ON PSD.fkIdUserAction = U.idUser
                WHERE PSD.idPackage = %s
                ORDER BY PSD.dateUser DESC
            """, (package_id,))
            rows = await cur.fetchall()
            estados_cambio = {"CANCEL", "RETURN", "DELETEPACKAGE", "CHANGECONTACTPOINT", "CANCELREQUEST"}
            timeline = []
            for row in rows:
                status = (row.get("status") or "").upper()
                id_user = row.get("idUser")
                evento = dict(row)
                if isinstance(evento.get("dateUser"), datetime):
                    evento["dateUser"] = evento["dateUser"].strftime("%Y-%m-%d %H:%M:%S")
                if status in estados_cambio:
                    evento["realizado_por"] = "cliente" if int(id_user) == 40220 else "moovin"
                timeline.append(evento)

            await cur.execute("""
                SELECT phone_digits, fullName, email, third_party_provider FROM package WHERE idPackage = %s LIMIT 1
            """, (package_id,))
            phone_row = await cur.fetchone()
            phone = phone_row["phone_digits"] if phone_row and phone_row.get("phone_digits") else None
            userName = phone_row["fullName"] if phone_row and phone_row.get("fullName") else None
            userEmail = phone_row["email"] if phone_row and phone_row.get("email") else None
            third_party_store = phone_row["third_party_provider"] if phone_row and phone_row.get("third_party_provider") else None
            return {
                "timeline": timeline,
                "telefono_dueño": phone,
                "nombre_dueño_paquete": userName,
                "email_dueño_paquete": userEmail,
                "tienda_donde_se_compro": third_party_store
            }

async def is_final_warehouse(pool, package_id):
    timeline = await get_package_historic(pool, package_id)
    return any(
        (row.get('idDelegate') is not None and int(row.get('idDelegate') or row.get('id_delegate') or 0) != 0)
        or (str(row.get('status')).upper() == "COORDINATE")
        for row in (timeline or [])
    )

async def rural_routes_schedule(canton, distrito):
    
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db="Text2Sql",
        port=DB_PORT,
        autocommit=True
    )
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT *
                    FROM rural_routes_schedule
                    WHERE canton = %s and distrito = %s
                """, (canton,distrito,))
                result = await cur.fetchall()
                return result
    finally:
        pool.close()
        await pool.wait_closed()

async def get_delivery_date(pool, enterprise_code: str) -> dict:
    package = await get_id_package(pool, enterprise_code)
    if not package:
        return {
            "Tracking": enterprise_code,
            "SLA_found": False,
            "SLA": "Paquete no encontrado"
        }
    timeline = await get_package_historic(pool, package)
    if timeline and str(timeline[0].get("status", "")).upper() in {"DELIVERED", "DELIVEREDCOMPLETE"}:
        return {
            "Tracking": package,
            "SLA_found": True,
            "SLA": "Paquete ya fue entregado"
        }
    delivery_address = await get_delivery_address(pool, package)
    last_date_in_moovin = await when__last_in_moovin(pool, package)
    if not last_date_in_moovin:
        return {
            "Tracking": package,
            "SLA_found": False,
            "SLA": "Paquete no ha llegado aun a Moovin"
        }

    hoy = datetime.now().date()

    if delivery_address == "GAM":
        fecha_moovin = datetime.strptime(str(last_date_in_moovin), "%Y-%m-%d %H:%M:%S")
        if fecha_moovin.date() == hoy:
            return {
                "Tracking": package,
                "SLA_found": True,
                "SLA": "24hrs"
            }
        else:
            return {
                "Tracking": package,
                "SLA_found": True,
                "SLA": "Hoy"
            }
    else:
        arrived_final_warehouse = await is_final_warehouse(pool, package)
        rural_schedule = None
        if isinstance(delivery_address, dict):
            canton = delivery_address.get("canton", "").upper()
            district = delivery_address.get("district", "").upper()
            rural_schedule_list = await rural_routes_schedule(canton, district)
            rural_schedule = rural_schedule_list[0] if rural_schedule_list else None

        if not rural_schedule:
            return {
                "Tracking": package,
                "SLA_found": False,
                "SLA": "Mantente atento a tu información de contacto, pronto te estaremos contactando para coordinar la fecha de entrega."
            }
            
        dias_semana = [
            ("lunes", "Lunes"),
            ("martes", "Martes"),
            ("miercoles", "Miércoles"),
            ("jueves", "Jueves"),
            ("viernes", "Viernes"),
            ("sabado", "Sábado"),
            ("domingo", "Domingo"),
        ]
        
        if arrived_final_warehouse:
            fecha_base = hoy
        else:
            fecha_moovin = datetime.strptime(str(last_date_in_moovin), "%Y-%m-%d %H:%M:%S")
            dias_transito = rural_schedule.get("dias_transito", 1)
            try:
                dias_transito = int(dias_transito)
            except Exception:
                dias_transito = 1
            fecha_base = (fecha_moovin + timedelta(days=dias_transito)).date()
        for i in range(7):
            fecha_entrega = fecha_base + timedelta(days=i)
            idx = fecha_entrega.weekday() 
            columna, nombre_dia = dias_semana[idx]
            if rural_schedule.get(columna): 
                fecha_formateada = f"{nombre_dia} {fecha_entrega.day} {fecha_entrega.strftime('%b')}"
                return {
                    "Tracking": package,
                    "SLA_found": True,
                    "SLA": fecha_formateada
                }
        return {
            "Tracking": package,
            "SLA_found": False,
            "SLA": "No hay días de entrega programados para esta ruta"
        }


#--------------------Funciones de chat_history--------------------#
async def get_agent_history(pool):
    """
    Obtiene el historial completo de la tabla sac_agent_memory,
    ordenado por user_id y fecha.
    Devuelve una lista de dicts.
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT *
                FROM sac_agent_memory
                ORDER BY user_id DESC, fecha DESC
            """)
            result = await cur.fetchall()
            return result
        
async def get_users_last_messages(pool):
    """
    Obtiene el último mensaje de cada usuario en la tabla sac_agent_memory,
    basado en la fecha más reciente. Devuelve una lista de dicts.
    Solo considera registros desde 2025-08-25 en adelante.
    """
    cutoff_str = "2025-08-25 00:00:00"

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT MAX(id) AS id
                FROM sac_agent_memory
                WHERE fecha >= %s
                GROUP BY user_id
                LIMIT 30
            """, (cutoff_str,))
            ids = await cur.fetchall()

            if not ids:
                return []

            id_list = tuple(row["id"] for row in ids)
            in_clause = ",".join(["%s"] * len(id_list))

            await cur.execute(f"""
                SELECT * 
                FROM sac_agent_memory
                WHERE id IN ({in_clause})
                ORDER BY fecha DESC
            """, id_list)

            return await cur.fetchall()

async def get_last_messages_by_user(pool, user_id: str, limit: int, last_id: int = None):
    """
    Devuelve los últimos `limit` mensajes de un usuario específico.
    Si se proporciona `last_id`, solo devuelve mensajes con `id` < `last_id`.
    Utiliza subconsulta por IDs para evitar problemas de memoria (buffer).
    """
    cutoff_str = "2025-08-25 00:00:00"

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if last_id:
                await cur.execute("""
                    SELECT id
                    FROM sac_agent_memory
                    WHERE user_id = %s
                      AND fecha >= %s
                      AND id < %s
                    ORDER BY fecha DESC
                    LIMIT %s
                """, (user_id, cutoff_str, last_id, limit))
            else:
                await cur.execute("""
                    SELECT id
                    FROM sac_agent_memory
                    WHERE user_id = %s
                      AND fecha >= %s
                    ORDER BY fecha DESC
                    LIMIT %s
                """, (user_id, cutoff_str, limit))

            rows = await cur.fetchall()
            if not rows:
                return []

            id_list = tuple(row["id"] for row in rows)
            in_clause = ",".join(["%s"] * len(id_list))

            await cur.execute(f"""
                SELECT *
                FROM sac_agent_memory
                WHERE id IN ({in_clause})
            """, id_list)

            results = await cur.fetchall()

            # Reordenar por fecha DESC para garantizar consistencia
            results.sort(key=lambda x: x["fecha"], reverse=True)

            return results

async def get_last_state(pool, user_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT id
                FROM sac_agent_memory
                WHERE user_id = %s
                ORDER BY fecha DESC
                LIMIT 1
            """, (user_id,))
            row = await cur.fetchone()
            if not row:
                return None
            await cur.execute("""
                SELECT * FROM sac_agent_memory WHERE id = %s
            """, (row['id'],))
            return await cur.fetchone()

async def save_message(pool, user_id, mensaje_entrante, mensaje_saliente, contexto):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if isinstance(contexto, BaseModel):
                contexto_json = contexto.model_dump_json()
            else:
                contexto_json = json.dumps(contexto)

            await cur.execute("""
                INSERT INTO sac_agent_memory (user_id, mensaje_entrante, mensaje_saliente, contexto)
                VALUES (%s, %s, %s, %s)
            """, (user_id, mensaje_entrante, mensaje_saliente, contexto_json))          
            
async def save_img_data(pool, user_id: str, user_message: str, images: list[str], mime_type: str = "image/jpeg") -> list[int]:
    """
    Guarda una lista de imágenes en base64 como registros binarios en la base de datos.
    
    Args:
        pool: pool de conexión MySQL (async).
        user_id (str): ID del usuario.
        user_message (str): mensaje de usuario asociado.
        images (list[str]): lista de strings base64.
        mime_type (str): tipo MIME (default: image/jpeg).
    
    Returns:
        list[int]: lista de IDs insertados.
    """
    inserted_ids = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for img_b64 in images:
                img_bytes = base64.b64decode(img_b64)
                await cur.execute("""
                    INSERT INTO sac_img_data (user_id, user_message, mime_type, data, date_created)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, user_message, mime_type, img_bytes, datetime.utcnow()))
                inserted_ids.append(cur.lastrowid)
        await conn.commit()
    return inserted_ids
#---------------------Env del Usuario que contacta--------------------#
async def get_user_env(pool, phone, whatsapp_username):
    phone = re.sub(r"\D", "", phone)
    try:
        if not phone.startswith("+"):
            phone = "+" + phone
            parsed = phonenumbers.parse(phone, None)
        else:
            parsed = phonenumbers.parse(phone, None)
        phone = str(parsed.national_number)
    except Exception as e:
        phone = re.sub(r"\D", "", phone)

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT idPackage, enterpriseCode, fkIdUser, fullName, email
                FROM package
                WHERE phone_digits = %s
                ORDER BY insertDate DESC
                LIMIT 3
            """, (phone,))
            paquetes = await cur.fetchall()

            if not paquetes:
                return {
                        "username": whatsapp_username,
                        "phone": phone, 
                        "paquetes": "No se encontraron paquetes para este usuario."
                        }

            nombres = ["Último paquete", "Penúltimo paquete", "Antepenúltimo paquete"]
            resultados = []
            nombre_usuario = paquetes[0]['fullName'] if paquetes[0].get('fullName') else "Usuario"
            email_usuario = paquetes[0]['email'] if paquetes[0].get('email') else "Sin correo registrado"

            for idx, paquete in enumerate(paquetes):
                id_package = paquete['idPackage']
                enterprise_code = paquete.get('enterpriseCode', 'N/A')
                await cur.execute("""
                    SELECT psd.dateServer, ps.description
                    FROM packageStatusDetailed psd
                    JOIN packageStatus ps ON psd.fkIdPackageStatus = ps.idPackageStatus
                    WHERE psd.idPackage = %s
                    ORDER BY psd.dateServer DESC
                    LIMIT 1
                """, (id_package,))
                estado = await cur.fetchone()
                if estado:
                    fecha_formateada = format_fecha(estado['dateServer'])
                    resultados.append({
                        "paquete": nombres[idx],
                        "tracking": f"{id_package} / {enterprise_code}",
                        "estado": estado['description'],
                        "fecha": fecha_formateada
                    })
                else:
                    resultados.append({
                        "paquete": nombres[idx],
                        "tracking": f"{id_package} / {enterprise_code}",
                        "estado": "Sin estados registrados."
                    })

            return {
                "username": nombre_usuario,
                "phone": phone,
                "email": email_usuario,
                "paquetes": resultados,
                
            }

async def get_img_data(pool, id: int) -> dict | None:
    query = "SELECT * FROM sac_img_data WHERE id = %s"
    print("Llamado a funcion que obtiene datos de paquetes")
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, (id,))
            result = await cursor.fetchone()
            return result