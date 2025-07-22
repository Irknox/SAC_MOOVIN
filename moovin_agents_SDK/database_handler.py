import aiomysql
from datetime import datetime
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
from pydantic import BaseModel
import re
import phonenumbers

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
def format_fecha(date_server):
    fecha_dt = datetime.strptime(str(date_server), "%Y-%m-%d %H:%M:%S")
    return fecha_dt.strftime("%A %d de %B %Y %H:%M")

async def create_tools_pool():
    return await aiomysql.create_pool(
        host=TOOLS_DB_HOST,
        user=TOOLS_DB_USER,
        password=TOOLS_DB_PASSWORD,
        db=TOOLS_DB_NAME,
        port=TOOLS_DB_PORT,
        autocommit=True
    )
    
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
    gam = await is_gam(pool, package)
    if gam:
        return "GAM"
    else:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT point.address, point.province, point.canton, point.district, point.latitude, point.longitude
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
                    IFNULL(PSD.value, '') AS value,
                    PSD.idPackageStatus,
                    PSD.dateUser,
                    PSD.executeAction,
                    PSD.infoControl,
                    (
                        SELECT name
                        FROM packageStatus
                        WHERE idPackageStatus = PSD.fkIdPackageStatus
                    ) AS status,
                    U.idUser,
                    CONCAT(U.name, ' ', U.lastName) AS fullName,
                    (
                        SELECT name
                        FROM userType
                        WHERE idUserType = U.fkIdUserType
                    ) AS userType,
                    PSD.id_delegate AS idDelegate,
                    d.name AS delegateName,
                    PSD.id_warehouse AS idWarehouse,
                    dw.warehouse_name AS warehouseName
                FROM packageStatusDetailed PSD
                INNER JOIN user U ON PSD.fkIdUserAction = U.idUser
                LEFT JOIN delegate d ON d.id_delegate = PSD.id_delegate
                LEFT JOIN delegates_warehouses dw ON dw.id_delegate = d.id_delegate AND dw.id_warehouse = PSD.id_warehouse
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
                    if int(id_user) == 40220:
                        evento["realizado_por"] = "cliente"
                    else:
                        evento["realizado_por"] = "moovin"
                timeline.append(evento)

            await cur.execute("""
                SELECT phone_digits, fullName FROM package WHERE idPackage = %s LIMIT 1
            """, (package_id,))
            phone_row = await cur.fetchone()
            phone = phone_row["phone_digits"] if phone_row and phone_row.get("phone_digits") else None
            userName = phone_row["fullName"] if phone_row and phone_row.get("fullName") else None
            return {
                "timeline": timeline,
                "telefono_dueño": phone,
                "nombre_dueño_paquete": userName
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
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Paso 1: obtener los IDs de los últimos registros de cada usuario
            await cur.execute("""
                SELECT MAX(id) as id
                FROM sac_agent_memory
                GROUP BY user_id
                LIMIT 50
            """)
            ids = await cur.fetchall()

            if not ids:
                return []

            # Paso 2: obtener los registros completos para esos IDs
            id_list = tuple(row["id"] for row in ids)
            in_clause = ",".join(["%s"] * len(id_list))

            await cur.execute(f"""
                SELECT * FROM sac_agent_memory
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
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Paso 1: obtener los IDs de los mensajes filtrados
            if last_id:
                await cur.execute("""
                    SELECT id
                    FROM sac_agent_memory
                    WHERE user_id = %s AND id < %s
                    ORDER BY fecha DESC
                    LIMIT %s
                """, (user_id, last_id, limit))
            else:
                await cur.execute("""
                    SELECT id
                    FROM sac_agent_memory
                    WHERE user_id = %s
                    ORDER BY fecha DESC
                    LIMIT %s
                """, (user_id, limit))

            rows = await cur.fetchall()
            if not rows:
                return []

            # Paso 2: obtener los registros completos por ID
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


