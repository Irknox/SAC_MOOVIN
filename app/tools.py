from langchain.tools import tool
import aiomysql
import os
from dotenv import load_dotenv
import asyncio
import locale
from datetime import datetime

#Formato en Español para la fecha
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

# ----------------- Configuración de MySQL ------------------
load_dotenv()
MYSQL_HOST = os.environ.get('Main_Db_Host')
MYSQL_USER = os.environ.get('Main_Db_User')
MYSQL_PASSWORD = os.environ.get('Main_Db_password')
MYSQL_DB = os.environ.get('Main_Db')
MYSQL_PORT = int(os.environ.get('Main_Db_Port'))

# ------------------ Tools ------------------#

@tool(description="Obtiene los últimos 3 estados de un paquete dado su enterpriseCode.")
def get_package_status(enterprise_code: str) -> dict:
    """
    Consulta la base de datos para obtener los últimos 3 estados del paquete
    identificado por enterprise_code, mostrando fecha (dateServer), enterpriseCode y descripción del estado.
    Devuelve un JSON estructurado.
    """
    async def query():
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
                # Obtener idPackage
                await cur.execute("""
                    SELECT idPackage 
                    FROM package 
                    WHERE enterpriseCode = %s
                """, (enterprise_code,))
                result = await cur.fetchone()
                if not result:
                    return {
                        "enterprise_code": enterprise_code,
                        "found": False,
                        "message": f"No se encontró ningún paquete con enterpriseCode {enterprise_code}.",
                        "estados": []
                    }

                id_package = result[0]

                # Obtener los últimos 3 registros de estado
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
                fecha_dt = datetime.strptime(str(date_server), "%Y-%m-%d %H:%M:%S")
                fecha_str = fecha_dt.strftime("%A %d de %B %Y %H:%M")
                estados.append({
                    "nombre_estado": nombres[idx] if idx < len(nombres) else f"Estado #{idx+1}",
                    "descripcion": status_desc,
                    "fecha": fecha_str
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

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        future = asyncio.ensure_future(query())
        import time
        while not future.done():
            time.sleep(0.01)
        return future.result()
    else:
        return loop.run_until_complete(query())


@tool(description="Obtiene la fecha de entrega de un paquete dado su enterpriseCode.")
def get_SLA() -> str:
    """
    Esta función es un placeholder para obtener el SLA de un paquete.
    Actualmente no implementada, pero se puede extender en el futuro.
    """
    return "Si tu paquete esta para ser entregado dentro de la GAM, deberías recibir tu paquete en un plazo de 24 horas una vez recibido. Si es fuera de la GAM, el plazo es de 2-3 días." 
# Lista de tools
TOOLS = [get_package_status,get_SLA]
