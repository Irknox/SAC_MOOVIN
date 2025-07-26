from agents import function_tool
from database_handler import get_package_historic, get_id_package
from mcp_handler import create_pickup_ticket,request_electronic_receipt


## ------------------ MCP Tools ------------------ ##
def Make_request_to_pickup_tool(pool):
    @function_tool(
        name_override="pickup_ticket",
        description_override="Crea un ticket de solicitud para retiro en sede de un paquete a partir de su Tracking o numero de seguimiento. Si el paquete existe y no ha sido entregado, solicita numero de seguimiento y descripcion del motivo del ticket."
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
            
        print(f"🛠️ Creando ticket de recogida para {package_id}... \n Tipo de dato: {type(package_id)}")
        owner_phone=package_historic.get("telefono_dueño","")
        print(f"📞 Dueño del paquete: {package_historic.get('nombre_dueño_paquete',"")} - Teléfono: {owner_phone}"
              f" - Email: {package_historic.get('email_dueño_paquete',''),} - Descripcion {description}")
        
        result = create_pickup_ticket(
                                    email=package_historic.get("email_dueño_paquete",""), 
                                    phone=owner_phone,
                                    name=package_historic.get("nombre_dueño_paquete"), 
                                    package_id=str(package_id), 
                                    description=description
                                    )
        return result

    return pickup_ticket

def Make_request_electronic_receipt_tool(pool):
    @function_tool(
        name_override="request_electronic_receipt_ticket",
        description_override="Crea un ticket de solicitud de factura electronica a partir de su Tracking o numero de seguimiento. Si el paquete existe y ha llegado a nuestras instalaciones, los parametros necesarios son: Numero de seguimiento, Cedula Juridica, Nombre Juridico, Direccion Completa y descripcion del motivo del ticket."
    )
    async def request_electronic_receipt_ticket(
        package: str,
        reason: str,
        legal_name: str,
        legal_id: str,
        full_address: str,
        
    ) -> dict:
        if not package or not reason or not legal_name or not legal_id or not full_address:
            return {"status": "error", "message": "Faltan datos necesarios para crear el ticket. Por favor, proporciona los datos faltantes"}
        package_id = await get_id_package(pool, package)
        if not package_id:
            return {"status": "error", "message": f"Paquete {package} no encontrado en la base de datos."}
        

        package_historic = await get_package_historic(pool, package_id)
        timeline=package_historic.get("timeline", [])
        
        inmoovin_encontrado = any(
            str(entry.get("status", "")).strip().upper() == "INMOOVIN"
            for entry in timeline
        )
        
        if not inmoovin_encontrado:
            return {
                "tracking": package_id,
                "package_found": True,
                "response": "Paquete aún no ha llegado a nuestras instalaciones. Una vez llegue, la solicitud podrá ser realizada."
            }
            
        print(f"🎫 Creando ticket para solicitud de factura electronica para {package_id}...")
        owner_phone=package_historic.get("telefono_dueño","")
        owner_info= {
            "email": package_historic.get("email_dueño_paquete",""),
            "phone": owner_phone,
            "name": package_historic.get("nombre_dueño_paquete")
        }
        print(f"Owner info: {type(owner_info)}")
        print(f"Tipos de dato: {type(str(package_id))}, {type(reason)}, {type(legal_name)}, {type(legal_id)}, {type(full_address)}")
        result = request_electronic_receipt(
                                    package_id=str(package_id), 
                                    reason=reason,
                                    legal_name=legal_name,
                                    legal_id=legal_id,
                                    full_address=full_address,
                                    owner=owner_info
                                    )
        return result

    return request_electronic_receipt_ticket