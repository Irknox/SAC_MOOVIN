from agents import function_tool, RunContextWrapper
from handlers.db_handlers import get_id_package,get_package_historic


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
        package_id = await get_id_package(pool, package_id)
        if not package_id:
            return {
                "status": "error", 
                "message": f"Paquete {package_id} no encontrado en la base de datos, estas seguro es este el paquete correcto?",
                "next_step":"Informa al agente los datos no coinciden con ningun paquete en la base de datos, pueden estar incorrectos, el agente deberia comprobar con el usuario los datos brindados."
                }
        try:
            historic = await get_package_historic(pool, package_id)
        except Exception as e:
            print(f"🔴 [ERROR] Fallo al obtener el histórico del paquete {package_id}: {e}")
            return {
                    "status":"error",
                    "message":"Hubo un problema al obtener el historial del paquete",
                    "next_step":"Informa al agente del error inmediatamente"
                    }
        phone_dueño = historic.get("telefono_dueño")
        if not phone_dueño:
            print(f"🔴 [ERROR] Telefono no disponible en la Base de Datos {historic}")
            return {
                    "status":"error",
                    "message": "Paquete no tiene telefono asociado en la Base de datos. en este caso no podre realizar la consulta",
                    "next_step":"Informa al agente que el paquete no tiene telefono asociado en la base de datos, la consulta no podra realizarse."
                    }
        if phone_dueño.strip().lower() != phone.strip().lower():
            print(f"🟠 [WARNING] Teléfono no coincide. Proporcionado: {phone}, Dueño: {phone_dueño}")
            return {
                    "status":"error",
                    "message": "El teléfono proporcionado no coincide con el dueño del paquete, podrias verificar el numero correcto",
                    "next_step":"Informa al agente que el telefono proporcionado no coincide con el del dueño del paquete, el agente deberia comprobar con el usuario el numero correcto."
                    }
        return {
            "status":"success",
            "timeline": historic.get("timeline","Dato no fue encontrado"),
            "Numero de Telefono": phone_dueño,
            "Dueño del Paquete": historic.get("nombre_dueño_paquete","Dato no fue encontrado"),
            "Tienda donde se compro el paquete":historic.get("tienda_donde_se_compro","Dato no fue encontrado")
        }

    return get_package_timeline