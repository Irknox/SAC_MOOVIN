import json
import redis
from datetime import datetime
import os
import pymongo
import aiomysql
from datetime import datetime, timedelta
from dotenv import load_dotenv

REDIS_URL = os.environ["REDIS_URL"]
rdb = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)

#Base de datos en MYSQL
MYSQL_HOST = os.environ.get('Db_HOST')
MYSQL_USER = os.environ.get('Db_USER')
MYSQL_PASSWORD = os.environ.get('Db_PASSWORD')
MYSQL_DB = os.environ.get('Db_NAME')
MYSQL_PORT = int(os.environ.get('Db_PORT', 3306))

# Base de datos para herramientas (Principal)
TOOLS_DB_HOST = os.environ.get('Main_Db_Host')
TOOLS_DB_USER = os.environ.get('Main_Db_User')
TOOLS_DB_PASSWORD = os.environ.get('Main_Db_password')
TOOLS_DB_NAME = os.environ.get('Main_Db')
TOOLS_DB_PORT = int(os.environ.get('Main_Db_Port', 3306))

REDISURL=os.environ.get('REDIS_URL')
REDISPASSWORD=os.environ.get('REDIS_PASSWORD')

#-------------------Pools-------------------#
async def create_mysql_pool():
    return await aiomysql.create_pool(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        port=MYSQL_PORT,
        autocommit=True
    )
    
async def create_tools_pool():
    return await aiomysql.create_pool(
        host=TOOLS_DB_HOST,
        user=TOOLS_DB_USER,
        password=TOOLS_DB_PASSWORD,
        db=TOOLS_DB_NAME,
        port=TOOLS_DB_PORT,
        autocommit=True
    )

def save_to_mongodb(sessions_collection: pymongo.collection.Collection, data: dict) -> bool:
    """Inserta el documento final de la sesión en la colección de MongoDB."""
    try:
        data["_id"] = data.pop("session_id", data.get("session_id", f"error_{datetime.now().timestamp()}"))
        def convert_to_datetime(iso_string):
            if isinstance(iso_string, str):
                return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            return iso_string
        data["init_date"] = convert_to_datetime(data.get("init_date"))
        data["finish_date"] = convert_to_datetime(data.get("finish_date"))
        result = sessions_collection.insert_one(data) 
        print(f"[INFO] Sesión guardada en Mongo: ID={result.inserted_id}, Resumen: {data.get('summary')}, Total Interacciones: {len(data.get('interactions',[]))}")
        return True
    except Exception as e:
        print(f"[ERROR] Falló la inserción en MongoDB para call_id={data.get('_id', 'Unknown')}: {e}")
        return False

def redis_key(call_id: str) -> str:
    """Clave para la metadata de la llamada (calls:{call_id})."""
    return f"calls:{call_id}"

def save_call_meta(call_id: str, meta: dict, ttl_seconds: int = 3600) -> None:
    """Guarda la metadata de la llamada en Redis (como String)."""
    rdb.set(redis_key(call_id), json.dumps(meta), ex=ttl_seconds)

def interaction_key(call_id: str) -> str:
    """Clave para la lista de interacciones (interactions:{call_id})."""
    return f"interactions:{call_id}"

def append_interaction(call_id: str, interaction_obj: dict) -> None:
    """Agrega una nueva interacción a la lista de Redis de forma atómica (RPUSH)."""
    interaction_json = json.dumps(interaction_obj)
    rdb.rpush(interaction_key(call_id), interaction_json)
    
def get_session_data(call_id: str) -> tuple[str | None, list]:
    """Recupera la metadata (JSON string) y la lista de interacciones (objetos Python) de Redis."""
    meta_json = rdb.get(redis_key(call_id))
    interactions_list_json = rdb.lrange(interaction_key(call_id), 0, -1)
    interactions_list = [json.loads(i) for i in interactions_list_json]
    return meta_json, interactions_list

def delete_session_data(call_id: str) -> None:
    """Limpia ambas claves de Redis al finalizar la sesión."""
    rdb.delete(redis_key(call_id))
    rdb.delete(interaction_key(call_id))
    
    
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