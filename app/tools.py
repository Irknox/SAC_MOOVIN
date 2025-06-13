from langchain.tools import tool
import aiomysql
import os
from dotenv import load_dotenv
import asyncio
import locale
from datetime import datetime
import openai
import json
from mcp.AI_router import run_mcp
from pydantic import BaseModel, Field

openai.api_key = os.environ.get("OPEN_AI_API")

# Formato en Español para la fecha
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

# ----------------- Configuración de MySQL ------------------
load_dotenv()
MYSQL_HOST = os.environ.get('Main_Db_Host')
MYSQL_USER = os.environ.get('Main_Db_User')
MYSQL_PASSWORD = os.environ.get('Main_Db_password')
MYSQL_DB = os.environ.get('Main_Db')
MYSQL_PORT = int(os.environ.get('Main_Db_Port'))


#--------------------Funciones auxiliares--------------------#
async def get_id_package(enterprise_code):
    """
    Intenta primero buscar idPackage usando el valor como un ID (int),
    si falla, entonces busca por enterpriseCode (str).
    """
    print(f"[get_id_package] Buscando idPackage para: {enterprise_code}")

    async with aiomysql.create_pool(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        port=MYSQL_PORT,
        autocommit=True
    ) as pool:

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

def format_fecha(date_server):
    fecha_dt = datetime.strptime(str(date_server), "%Y-%m-%d %H:%M:%S")
    return fecha_dt.strftime("%A %d de %B %Y %H:%M")

def run_async_query(query_func):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        future = asyncio.ensure_future(query_func())
        import time
        while not future.done():
            time.sleep(0.01)
        return future.result()
    else:
        return loop.run_until_complete(query_func())

def TracerAI(timeline_data: dict, model: str = "gpt-4") -> str:
    """
    Envía el resultado de get_package_timeline a un modelo LLM con un prompt personalizado
    y devuelve la interpretación del historial del paquete.
    """
    with open("app/prompt_TracerAI.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()
   
    if not timeline_data.get("found", False) or not timeline_data.get("estados"):
        return timeline_data.get("message", "No hay información para interpretar.")

    # Preparar entrada como JSON formateado
    timeline_json = json.dumps(timeline_data, indent=2, ensure_ascii=False)
    full_prompt = f"Aquí tienes el historial:\n{timeline_json}"
    
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[TracerAI][ERROR] Fallo la llamada a OpenAI: {e}")
        return "Error interno: no se pudo obtener la interpretación del historial."

# ------------------ Tools ------------------#

@tool(description="Obtiene los últimos 3 estados de un paquete dado su enterpriseCode.")
def get_package_status(enterprise_code: str) -> dict:
    async def query():
        id_package = await get_id_package(enterprise_code)
        if not id_package:
            return {
                "enterprise_code": enterprise_code,
                "found": False,
                "message": f"No se encontró ningún paquete con enterpriseCode {enterprise_code}.",
                "estados": []
            }
        pool = await aiomysql.create_pool(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            port=MYSQL_PORT,
            autocommit=True
        )
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT psd.dateServer, p.enterpriseCode, ps.description
                    FROM packageStatusDetailed psd
                    JOIN packageStatus ps ON psd.fkIdPackageStatus = ps.idPackageStatus
                    JOIN package p ON psd.idPackage = p.idPackage
                    WHERE psd.idPackage = %s
                    ORDER BY psd.dateServer DESC
                    LIMIT 3
                """, (id_package,))
                rows = await cur.fetchall()
        pool.close()
        await pool.wait_closed()

        if rows:
            estados = []
            nombres = ["Último estado", "Penúltimo estado", "Estado trasanterior"]
            for idx, row in enumerate(rows):
                date_server, _, status_desc = row
                estados.append({
                    "nombre_estado": nombres[idx] if idx < len(nombres) else f"Estado #{idx+1}",
                    "descripcion": status_desc,
                    "fecha": format_fecha(date_server)
                })
            return {
                "enterprise_code": enterprise_code,
                "found": True,
                "estados": estados
            }
        else:
            return {
                "enterprise_code": enterprise_code,
                "found": True,
                "message": "No se encontraron registros de estado para el paquete.",
                "estados": []
            }
    return run_async_query(query)

@tool(description="Obtiene la fecha de entrega de un paquete dado su enterpriseCode.")
def get_SLA() -> str:
    """
    Esta función es un placeholder para obtener el SLA de un paquete.
    Actualmente no implementada, pero se puede extender en el futuro.
    """
    return "Si tu paquete esta para ser entregado dentro de la GAM, deberías recibir tu paquete en un plazo de 24 horas una vez recibido. Si es fuera de la GAM, el plazo es de 2-3 días." 

@tool(description="Obtiene el Timeline de un paquete dado su enterpriseCode.")
def get_package_timeline(enterprise_code: str) -> str:
    async def query():
        id_package = await get_id_package(enterprise_code)
        if not id_package:
            return {
                "enterprise_code": enterprise_code,
                "found": False,
                "message": f"No se encontró ningún paquete con enterpriseCode {enterprise_code}.",
                "estados": []
            }
        pool = await aiomysql.create_pool(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            port=MYSQL_PORT,
            autocommit=True
        )
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT psd.dateServer, p.enterpriseCode, ps.description, psd.fkIdUserAction, psd.fkIdPackageStatus
                    FROM packageStatusDetailed psd
                    JOIN packageStatus ps ON psd.fkIdPackageStatus = ps.idPackageStatus
                    JOIN package p ON psd.idPackage = p.idPackage
                    WHERE psd.idPackage = %s
                    ORDER BY psd.dateServer DESC
                """, (id_package,))
                rows = await cur.fetchall()
        pool.close()
        await pool.wait_closed()

        estados = []
        estados_cambio = {16, 14, 27, 31, 17}
        if rows:
            for idx, row in enumerate(rows):
                date_server, _, status_desc, fkIdUserAction, fkIdPackageStatus = row
                estado = {
                    "numero_estado": idx + 1,
                    "descripcion": status_desc,
                    "fecha": format_fecha(date_server)
                }
                if fkIdPackageStatus in estados_cambio:
                    if int(fkIdUserAction) == 40220:
                        realizado_por = "cliente"
                    else:
                        realizado_por = "moovin"
                    estado["realizado_por"] = realizado_por
                estados.append(estado)
            return {
                "enterprise_code": enterprise_code,
                "found": True,
                "estados": estados
            }
        else:
            return {
                "enterprise_code": enterprise_code,
                "found": True,
                "message": "No se encontraron registros de estado para el paquete.",
                "estados": []
            }
    timeline = run_async_query(query)
    trace_result = TracerAI(timeline)
    return trace_result


    action: str = Field(..., description="Acción a ejecutar, por ejemplo: 'create_ticket', 'get_human'")
    data: dict = Field(default_factory=dict, description="Datos adicionales necesarios para la acción")
    
@tool(description="Agente AI que ejecuta acciones en el MCP. Usalo para crear tickets, notificar humanos, debe ser un string con la informacion del usuario para el ticket")
def run_mcp_action(instruccion: str) -> str:
    return run_mcp(instruccion)

# Lista de tools
TOOLS = [get_package_timeline, get_package_status, get_SLA, run_mcp_action]
