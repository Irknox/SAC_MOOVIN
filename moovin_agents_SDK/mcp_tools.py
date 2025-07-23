from agents import function_tool
from database_handler import get_package_historic, get_id_package
from mcp_handler import create_pickup_ticket


## ------------------ MCP Tools ------------------ ##
def Make_request_to_pickup_tool(pool):
    @function_tool(
        name_override="pickup_ticket",
        description_override="Crea un ticket de recogida para un paquete a partir de su Tracking o numero de seguimiento. Si el paquete existe y no ha sido entregado, solicita numero de seguimiento y descripcion del motivo del ticket."
    )
    async def pickup_ticket(
        package: str,
        description: str 
    ) -> dict:
        if not package or not description:
            return {"status": "error", "message": "Faltan datos necesarios para crear el ticket. Por favor, proporciona el número de seguimiento y una descripción del motivo."}
        package_id = await get_id_package(pool, package)
        if not package_id:
            return {"status": "error", "message": f"Paquete {package} no encontrado en la base de datos."}
        

        package_historic = await get_package_historic(pool, package_id)
        timeline=package_historic.get("timeline", [])
        if timeline and str(timeline[0].get("status", "")).upper() in {"DELIVERED", "DELIVEREDCOMPLETE"}:
            return {
                "tracking": package_id,
                "package_found": True,
                "response": "Paquete ya fue entregado"
            }
            
        print(f"🛠️ Creando ticket de recogida para {package_id}...")
        owner_phone=package_historic.get("telefono_dueño","")
        print(f"📞 Dueño del paquete: {package_historic.get('nombre_dueño_paquete',"")} - Teléfono: {owner_phone}")
        
        result = create_pickup_ticket(
                                    email=package_historic.get("email_dueño_paquete",""), 
                                    phone=owner_phone,
                                    name=timeline["nombre_dueño_paquete"], 
                                    package_id=package_id, description=description
                                    )
        return result

    return pickup_ticket