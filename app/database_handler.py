import aiomysql
from datetime import datetime

#--------------------Funciones auxiliares--------------------#
def format_fecha(date_server):
    fecha_dt = datetime.strptime(str(date_server), "%Y-%m-%d %H:%M:%S")
    return fecha_dt.strftime("%A %d de %B %Y %H:%M")


#--------------------Funciones de chat_history--------------------#
async def get_history(pool, session_id, limit=15):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT user_message, agent_response, timestamp
                FROM chat_history
                WHERE session_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (session_id, limit))
            results = await cur.fetchall()
            results = list(results)
            results.reverse()
            return results

async def save_message(pool, session_id, user_message, agent_response):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO chat_history (session_id, user_message, agent_response) 
                VALUES (%s, %s, %s)
            """, (session_id, user_message, agent_response))
            
#---------------------Env del Usuario que contacta--------------------#
async def get_user_env(pool, phone):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT idPackage, enterpriseCode, fkIdUser, fullName
                FROM package
                WHERE phone_digits = %s
                ORDER BY insertDate DESC
                LIMIT 3
            """, (phone,))
            paquetes = await cur.fetchall()
            if not paquetes:
                return "No se encontraron paquetes para este usuario."
            nombres = ["Último paquete", "Penúltimo paquete", "Antepenúltimo paquete"]
            resultados = []
            nombre_usuario = paquetes[0]['fullName'] if paquetes[0].get('fullName') else "Usuario"
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
                    resultados.append(
                        f"{nombres[idx]}: Tracking: {id_package} / {enterprise_code} | Último estado: {estado['description']} | Fecha: {fecha_formateada}"
                    )
                else:
                    resultados.append(
                        f"{nombres[idx]}: Tracking: {id_package} / {enterprise_code} | Sin estados registrados."
                    )
            respuesta = f"Nombre de la persona que contacta por Whatsapp: {nombre_usuario}\n" + "\n".join(resultados)
            print(f"[DEBUG] get_user_env respuesta: {respuesta}")
            return respuesta