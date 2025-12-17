from agents import function_tool, RunContextWrapper
from handlers.db_handlers import get_id_package,get_package_historic
from handlers.aux_handlers import create_pickup_ticket

DELIVERED_STATES= {"DELIVERED", "DELIVEREDCOMPLETE"}
RETURN_STATES= {"RETURN"}
FAILED_STATES= {"FAILED","DELETEPACKAGE","CANCELNOCHARGE","CANCEL"}

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

##-----------------------Ticketing Tools -----------------------##
def Make_request_to_pickup_tool(pool):
    @function_tool(
        name_override="pickup_instore_ticket",
        description_override="Crea un ticket de solicitud para retiro en sede de un paquete a partir de su Tracking o número de seguimiento. Si el paquete existe y no ha sido entregado ni presenta retornos/fallas la solicitud puede ser procesada, de lo contrario no. Numero de seguimiento y descripcion/motivo son los parametros obligatorios."
    )
    async def pickup_instore_ticket(
        package: str,
        description: str
    ) -> dict:
        if not package or not description:
            return {
                "status": "error",
                "message": "Faltan datos, para crear la solicitud, por favor revisa los datos proporcionados",
                "next_step":"Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario."
                }
        package_id = await get_id_package(pool, package)
        if not package_id:
            return {
                "status": "error",
                "message": f"Paquete {package} no encontrado en la base de datos",
                "next_step":"Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario."      
                }
        package_historic = await get_package_historic(pool, package_id)
        timeline = package_historic.get("timeline", []) or []
        statuses = [str(e.get("status", "")).strip().upper() for e in timeline]
        blockers = []
        if any(s in DELIVERED_STATES for s in statuses):
            blockers.append("DELIVERED")
        if any(s in RETURN_STATES for s in statuses):
            blockers.append("RETURN")
        failed_count = sum(1 for s in statuses if s in FAILED_STATES)
        if failed_count > 2:
            blockers.append("FAILED")
        if blockers:
            return {
                "tracking": str(package_id),
                "package_found": True,
                "status": "error",
                "message": "Solciitud no puede ser procesada, ya que el paquete se encuentra en estado: ".join(blockers),
                "next_step":"Informa al agente del error inmediatamente."                    
            }
        print(f"🛠️ Creando ticket de recogida para {package_id}...  Tipo de dato: {type(package_id)}")
        owner_phone = package_historic.get("telefono_dueño", "") or package_historic.get("telefono_dueño_paquete", "")
        owner_name  = package_historic.get("nombre_dueño_paquete", "")
        owner_mail  = package_historic.get("email_dueño_paquete", "")

        result = create_pickup_ticket(
            email=owner_mail,
            phone=owner_phone,
            name=owner_name,
            package_id=str(package_id),
            description=description
        )

        ticketNumber=result.get("ticket_number")
        DevURL=result.get("webUrl","Desconocido") #URL de desarrollo del ticket en Zoho, puede ser guardado para tracing
        response={
            "status":"success",
            "TicketNumber":ticketNumber,
            "message":"Ticket creado exitosamente",
        }        
        return response

    return pickup_instore_ticket