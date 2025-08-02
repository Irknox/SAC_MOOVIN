from agents import function_tool,RunContextWrapper
from database_handler import get_package_historic, get_id_package, get_img_data,get_delivery_address,reverse_geocode_osm,send_location_to_whatsapp
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
        ctx.context.imgs_ids=[]
        return result

    return package_damaged_ticket

def Make_send_delivery_address_requested_tool():
    @function_tool(
    name_override="send_delivery_address_requested",
    description_override="Envia al usuario la direccion enviada por el usuario para el cambio de direccion, usala para que el usuario confirme la direccion que desea " 
    )
    async def send_delivery_address_requested(
        ctx: RunContextWrapper,
    ) -> dict:
        print (f"🌎 Enviando la direcciona que desea cambiar el usuario como confirmacion....")
        print (f"Contexto que esta siendo usado {ctx.context}")
        cordinates_info=ctx.context.location_sent       
        lat=cordinates_info.get("latitude")
        lng=cordinates_info.get("longitude")
        print (f"Enviando direccion a usario con longitud {lng} y latitud {lat}")
        try:
            address_response =reverse_geocode_osm(lat, lng)
            address_data=address_response.get("address",{})
            user_id=ctx.context.user_id
            if address_data:
                town_name=address_data.get("road",None)
                full_address=address_response.get("display_name", None)
                if town_name and full_address:
                    is_message_sent=await send_location_to_whatsapp(user_id,lat,lng,town_name,full_address)
                    message_sent_data=is_message_sent.json()
                    message=message_sent_data.get("message", None)
                    location_data=message.get("locationMessage",None)
                    if location_data:
                        address=location_data.get("address")
                        return {
                            "status": "Success, message with ubication in ubication format was sent to user",
                            "address pre info": address
                        }
        except Exception as e:
            print(f"❌ Error al enviar la direccion al usuario: {e}")
            return "[Error al enviar direccion al usuario]"
        
        
        
    return send_delivery_address_requested

def Make_change_delivery_address_tool():
    @function_tool(
    name_override="change_delivery_address",
    description_override="Cambia la direccion de entrega para un paquete, el numero de seguimiento, numero de telefono del paquete, confirmacion de cambio y confirmacion de nueva direccion son los parametros necesarios. " 
    )
    async def change_delivery_address(
        ctx:RunContextWrapper,
        package: str,
        is_new_address_confirmed:bool,
        is_request_confirmed:bool
    ) -> dict:
        print (f"Cambiando direccion de paquete para paquete {package}...") 
        print (f"Datos recibidos: Nueva direccion confirmada: {is_new_address_confirmed}, Request confirmado: {is_request_confirmed}")
        
        new_address=ctx.context.location_sent
        if not new_address:
            return {
                "status": "error",
                "reason": "New Delivery Address hasn't been provided"
            }
            
        if not is_new_address_confirmed or not is_request_confirmed:
            return {
                "status": "denied",
                "reason": "New address or request confirmation hasn't been done yet"
            }
        return {
            "status": "In Progress",
            "reason":"Developers testing face"
        }
    return change_delivery_address