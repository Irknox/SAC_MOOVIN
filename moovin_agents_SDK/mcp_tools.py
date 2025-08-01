from agents import function_tool,RunContextWrapper
from database_handler import get_package_historic, get_id_package, get_img_data
from mcp_handler import create_pickup_ticket,request_electronic_receipt, report_package_damaged


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
        
        owner_info= {
            "email": package_historic.get("email_dueño_paquete",""),
            "phone": package_historic.get("telefono_dueño",""),
            "name": package_historic.get("nombre_dueño_paquete")
        }
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

def Make_package_damaged_tool(mysql_pool,tools_pool):
    @function_tool(
        name_override="package_damaged_ticket",
        description_override="Crea un ticket para reportar el daño de un paquete a partir de su Tracking o número de seguimiento. Si el paquete existe y ha sido entregado, solicita número de seguimiento, descripción del daño y fotos del daño."
    )
    async def package_damaged_ticket(
        ctx: RunContextWrapper,
        package: str,
        description: str
    ) -> dict:
        print(f"Intentado crear ticket para paquete {package} con descripcion {description}")
        if not package or not description:
            return {
                "status": "error",
                "message": "Faltan datos necesarios para crear el ticket. Proporciona número de seguimiento y descripción del daño."
            }

        package_id = await get_id_package(tools_pool, package)
        
        if not package_id:
            return {"status": "error", "message": f"Paquete {package} no encontrado en la base de datos."}

        package_historic = await get_package_historic(tools_pool, package_id)
        timeline = package_historic.get("timeline", [])

        if not timeline or str(timeline[0].get("status", "")).upper() not in {"DELIVERED", "DELIVEREDCOMPLETE"}:
            return {
                "tracking": package_id,
                "package_found": True,
                "response": "Este ticket solo puede generarse para paquetes que ya hayan sido entregados."
            }

        owner_info = {
            "email": package_historic.get("email_dueño_paquete", ""),
            "phone": package_historic.get("telefono_dueño", ""),
            "name": package_historic.get("nombre_dueño_paquete", "")
        }

        img_data_result = []
        print (f"[Debugg] Intentado obtener data de imagenes con ids {ctx.context.imgs_ids}")
        if ctx.context.imgs_ids:
            for img_id in ctx.context.imgs_ids:
                try:
                    row = await get_img_data(mysql_pool, img_id)
                    if row and row.get("data"):
                        img_data_result.append(row["data"])
                except Exception as e:
                    print(f"⚠️ Error recuperando imagen {img_id}: {e}")

        print(f"📦 Reporte de paquete dañado con {len(img_data_result)} imágenes recuperadas. Datos: {img_data_result}")
        
        result = report_package_damaged(
            owner=owner_info,
            package_id=str(package_id),
            description=description,
            img_data=img_data_result
        )

        return result

    return package_damaged_ticket