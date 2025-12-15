from agents import function_tool,RunContextWrapper
from handlers.main_handler import get_package_historic, get_id_package, get_img_data,get_delivery_address,reverse_geocode_osm,send_location_to_whatsapp
from handlers.mcp_handler import _parse_date_cr,create_pickup_ticket, escalate_to_zoho, request_electronic_receipt, report_package_damaged,change_delivery_address as change_delivery_address_request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from tools import is_admin
from typing import Optional

CR_TZ = ZoneInfo("America/Costa_Rica")


admins={
    "50671474099@s.whatsapp.net": "Milagro Fallas",
    "50662587119@s.whatsapp.net": "Alejandro Carmona"
}

DELIVERED_STATES= {"DELIVERED", "DELIVEREDCOMPLETE"}
RETURN_STATES= {"RETURN"}
FAILED_STATES= {"FAILED","DELETEPACKAGE","CANCELNOCHARGE","CANCEL"}
## ------------------ MCP Tools ------------------ ##
def Make_request_to_pickup_tool(pool):
    @function_tool(
        name_override="pickup_ticket",
        description_override="Crea un ticket de solicitud para retiro en sede de un paquete a partir de su Tracking o número de seguimiento. Si el paquete existe y no ha sido entregado ni presenta retornos/fallas, solicita número de seguimiento y descripción del motivo."
    )
    async def pickup_ticket(
        ctx: RunContextWrapper,
        package: str,
        description: str
    ) -> dict:
        if not package or not description:
            return {
                "status": "error",
                "message": "Faltan datos, para crear la solicitud, por favor revisa los datos proporcionados",
                "next_step":"Informa al usuario del error inmediatamente."
                }
            

        package_id = await get_id_package(pool, package)
        if not package_id:
            return {
                "status": "error",
                "message": f"Paquete {package} no encontrado en la base de datos, estas seguro esta es el paquete correcto?",
                "next_step":"Informa al usuario del error inmediatamente."      
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
                "next_step":"Informa al usuario del error inmediatamente."                    
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
        DevURL=result.get("webUrl","Desconocido")
        if ctx.context.issued_tickets_info is None:
            ctx.context.issued_tickets_info = []
        ctx.context.issued_tickets_info.insert(0,{"TicketNumber":ticketNumber,"DevURL":DevURL})
        
        response={
            "status":"success",
            "TicketNumber":ticketNumber,
            "message":"Ticket creado exitosamente",
        }        
        return response

    return pickup_ticket

def Make_request_electronic_receipt_tool(pool):
    @function_tool(
        name_override="request_electronic_receipt_ticket",
        description_override="Crea un ticket de solicitud de factura electronica a partir de su Tracking o numero de seguimiento. Si el paquete existe y ha llegado a nuestras instalaciones, los parametros necesarios son: Numero de seguimiento, Cedula Juridica, Nombre Juridico, Direccion Completa y descripcion del motivo del ticket."
    )
    async def request_electronic_receipt_ticket(
        ctx: RunContextWrapper,
        package: str,
        reason: str,
        legal_name: str,
        legal_id: str,
        full_address: str,
        
    ) -> dict:
        if not package or not reason or not legal_name or not legal_id or not full_address:
            
            return {
                    "status": "error", 
                    "message": "Faltan datos necesarios para crear el ticket, revisa los datos enviados.",
                    "next_step":"Informa al usuario del error inmediatamente."
                    }
            
        package_id = await get_id_package(pool, package)
        if not package_id:
            return {
                    "status": "error",
                    "message": f"El Paquete {package} no encontrado en la base de datos, estas seguro este es el numero de paquete?",
                    "next_step":"Informa al usuario del error inmediatamente."
                    }
        

        package_historic = await get_package_historic(pool, package_id)
        timeline=package_historic.get("timeline", [])
        
        inmoovin_encontrado = any(
            str(entry.get("status", "")).strip().upper() == "INMOOVIN"
            for entry in timeline
        )
        
        if not inmoovin_encontrado:
            return {
                "status":"error",
                "tracking": package_id,
                "package_found": True,
                "message": "Paquete aún no ha llegado a nuestras instalaciones. Una vez llegue, la solicitud podrá ser realizada",
                "next_step":"Informa al usuario del error inmediatamente."
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
        try:
            result_data=result
            ticketNumber=result_data.get("TicketNumber")
            DevURL=result_data.get("DevURL","Desconocido")
            if ctx.context.issued_tickets_info is None:
                ctx.context.issued_tickets_info = []

            new_ticket = {"TicketNumber": ticketNumber, "DevURL": DevURL}
            ctx.context.issued_tickets_info.insert(0, new_ticket)
            
            response ={
                "status":"success",
                "TicketNumber":ticketNumber,
                "message":"Ticket creado exitosamente",
            }
            return response
        except Exception as e:
            print(f"⚠️ Error al crear ticket para factura electronica")
            return {
                    "status":"error",
                    "message":"Ocurrio un error al crear el ticket",
                    "next_step":"Informa al usuario del error inmediatamente."
                    }

    return request_electronic_receipt_ticket

def Make_package_damaged_tool(mysql_pool, tools_pool):
    @function_tool(
        name_override="package_damaged_ticket",
        description_override="Crea un ticket para reportar el daño de un paquete a partir de su Tracking o número de seguimiento. Solo procede si el último estado del paquete es DELIVERED y han pasado más de 48 horas desde esa entrega. Requiere número de seguimiento, descripción del daño y fotos."
    )
    async def package_damaged_ticket(
        ctx: RunContextWrapper,
        package: str,
        description: str
    ) -> dict:
        print(f"🔨 Intentando crear ticket para paquete dañado. Tracking: {package} | Desc: {description}")

        if not package or not description or not ctx.context.imgs_ids:
            return {
                "status": "error",
                "message": "Faltan datos para crear el ticket. Asegurate de proporcionar el tracking, descripción del daño y al menos 1 imagen.",
                "next_step":" Informa al usuario del error inmediatamente."                    
                }

        package_id = await get_id_package(tools_pool, package)
        if not package_id:
            return {
                    "status": "error", 
                    "message": f"Paquete {package} no encontrado en la base de datos. Estas seguro este es el paquete correcto?",
                    "next_step":"Informa al usuario del error inmediatamente."
                    }

        package_historic = await get_package_historic(tools_pool, package_id)
        timeline = package_historic.get("timeline", []) or []
        if not timeline:
            return {
                "status": "error", 
                "tracking": str(package_id),
                "package_found": True,
                "message": "No hay historial de estados para este paquete.",
                "next_step":" Informa al usuario del error inmediatamente." 
            }

        last_event = timeline[0]
        last_status = str(last_event.get("status", "")).strip().upper()
        last_date_str = last_event.get("dateUser")
        last_dt = _parse_date_cr(last_date_str)
        now_cr = datetime.now(CR_TZ)

        if last_status not in DELIVERED_STATES:
            return {
                "status":"error",
                "tracking": str(package_id),
                "package_found": True,
                "message": "Este ticket solo puede en las primeras 48 horas después de la entrega.",
                "next_step":" Informa al usuario del error inmediatamente." 
            }
            
        if not last_dt:
            return {
                "status":"error",
                "tracking": str(package_id),
                "package_found": True,
                "message": "No se pudo validar la fecha de entrega del paquete.",
                "next_step":" Informa al usuario del error inmediatamente." 
            }

        hours_since = (now_cr - last_dt).total_seconds() / 3600.0
        if hours_since >= 48:
            return {
                "status":"error",                
                "tracking": str(package_id),
                "package_found": True,
                "message": (
                    f"Este ticket solo puede en las primeras 48 horas después de la entrega. "
                    f"Última entrega: {last_date_str} (hace ~{int(hours_since)} horas)."
                ),
                "next_step":" Informa al usuario del error inmediatamente." 
            }

        owner_info = {
            "email": package_historic.get("email_dueño_paquete", "") or package_historic.get("email_duenho_paquete", ""),
            "phone": package_historic.get("telefono_dueño", "") or package_historic.get("telefono_dueño_paquete", ""),
            "name":  package_historic.get("nombre_dueño_paquete", "") or package_historic.get("nombre_duenho_paquete", "")
        }

        img_data_result = []
        for img_id in (ctx.context.imgs_ids or []):
            try:
                row = await get_img_data(mysql_pool, img_id)
                if row and row.get("data"):
                    img_data_result.append(row["data"])
            except Exception as e:
                print(f"⚠️ Error recuperando imagen {img_id}: {e}")

        print(f"📦 Reporte de paquete dañado con {len(img_data_result)} imagen(es) recuperada(s).")

        result = report_package_damaged(
            owner=owner_info,
            package_id=str(package_id),
            description=description,
            img_data=img_data_result
        )

        if result.get("status") == "ok":
            print("✅ Ticket creado con éxito")
            ctx.context.imgs_ids = []
            ticketNumber=result.get("Numero de Ticket")
            DevURL=result.get("webUrl","Desconocido")
            if ctx.context.issued_tickets_info is None:
                ctx.context.issued_tickets_info = []
            ctx.context.issued_tickets_info.insert(0,{"TicketNumber":ticketNumber,"DevURL":DevURL})
            return {
                "status": "success",
                "TicketNumber": ticketNumber,
                "message":"Ticket creado exitosamente",
            }
        else:
            print(f"❌ Error al crear el ticket: {result}")
            return {
                "status": "error",
                "message": "Ocurrió un error al crear el ticket.",
                "next_step":" Informa al usuario del error inmediatamente." 
            }

    return package_damaged_ticket

def Make_send_delivery_address_requested_tool():
    @function_tool(
    name_override="send_delivery_address_requested",
    description_override="Envia al usuario la direccion enviada por el usuario para el cambio de direccion, usala para que el usuario confirme la direccion que desea " 
    )
    async def send_delivery_address_requested(
        ctx: RunContextWrapper,
    ) -> dict:
        print (f"🌎 Enviando la direccion que desea cambiar el usuario como confirmacion....")
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
                        if "confirmations" in ctx.context.location_sent:
                            ctx.context.location_sent["confirmations"]["is_new_address_confirmed"] = True
                            print(f"Valor actuailizado del contexto de location {cordinates_info}")
                        else:
                            print(f"confirmation was not found in context")
                        return {
                            "status": "success",
                            "message":"Message with Ubication was sent and received by the User",
                            "address pre info": address,
                            "location_data":{
                                "latitude":lat,
                                "longitude":lng
                            }
                        }
        except Exception as e:
            print(f"❌ Error al enviar la direccion al usuario: {e}")
            return {
                "status":"error",
                "message":"Ocurrio un error al enviar la ubicacion solicitada",
                "next_step":"Informa al usuario del error inmediatamente"
            }
        
    return send_delivery_address_requested

def Make_change_delivery_address_tool(pool):
    @function_tool(
    name_override="change_delivery_address",
    description_override="Cambia la direccion de entrega para un paquete, el numero de seguimiento y numero de telefono del paquete son necesarios, ademas, antes de usar esta herramienta es necesario el uso de send_delivery_address_requested y send_current_delivery_address para confirmaciones. " 
    )
    async def change_delivery_address(
        ctx:RunContextWrapper,
        package: str,
    ) -> dict:
        print (f"🧭 Cambiando direccion de paquete para paquete {package}...") 
        
        new_address=ctx.context.location_sent
        if new_address.get("is_request_confirmed_by_user") == False:
            return {
                "status":"error",
                "message":"Debo enviarte la ubicacion actual para confirmar si realmente deseas confirmar la direccion",
                "next_step":"Envia la ubicacion actual usando la herramienta send_current_delivery_address"
                }
        if new_address.get("is_new_address_confirmed") == False:
            return {
                "status":"error", 
                "message":"No he confirmado la nueva direccion que deseas añadir a tu paquete",
                "next_step":"Envia la ubicacion actual usando la herramienta send_delivery_address_requested"
                }
        
        package_id = await get_id_package(pool, package)
        if not package_id:
            return {
                    "status": "error",
                    "message": f"Paquete {package} no encontrado en la base de datos. Estas seguro es el paquete correcto?",
                    "next_step":"Informa al Usuario del error inmediatamente"
                    }

        package_historic = await get_package_historic(pool, package_id)
        timeline=package_historic.get("timeline", [])
        # if timeline and str(timeline[0].get("status", "")).upper() in {"DELIVERED", "DELIVEREDCOMPLETE"}:
        #     return {
        #         "tracking": package_id,
        #         "package_found": True,
        #         "response": "Paquete ya fue entregado, por lo tanto la solicitud para el cambio de direccion no es posible."
        #     }
            
        package_info = await get_delivery_address(pool, package_id)
        id_point=package_info.get("idPoint")
        if not id_point:
            print (f"No se obtuvo el id point f{package_info}")
            return {
                    "status": "error", 
                    "message": "No se encontró el punto de entrega para este paquete.",
                    "next_step":"Informa al Usuario del error inmediatamente"
                    }
        
        
        lat=new_address.get("latitude")
        lng=new_address.get("longitude")
        delivery_address_request= await change_delivery_address_request(id_point,lat,lng)
        delivery_change_request_data=delivery_address_request.json() 
        if delivery_change_request_data.get("status") == "SUCCESS":
            ctx.context.location_sent = {}
            return {
                "status": "success",
                "message":"Delivery address changed"
            }
        elif delivery_change_request_data.get("message") == "Not exist package":
            print(f"⚠️ Error al cambiar la direccion de entrega, el paquete no ha sido anadido a la BD en Dev aun")
            ctx.context.location_sent = {}
            return {
                "status":"error",
                "message":"El paquete no ha sido añadido a la Base de datos de Desarrollo",
                "next_step":"Informa al Usuario del error inmediatamente"
            }
        else:
            print(f"⚠️ Error al cambiar la direccion de entrega")
            return {
                "status":"error",
                "message":"Un error ocurrio al cambiar la direccion de Entrega",
                "next_step":"Informa al Usuario del error inmediatamente"
            }
    return change_delivery_address

def Make_escalate_to_human(pool):
    @function_tool(
    name_override="escalate_to_human",
    description_override=(
    "Dado un correo, telefono o ambos y una descripcion se crea un Ticket en Zoho Desk para informar a un Agente Humano sobre la situacion que esta siendo escalada."
    "Puede ser usada unicamente si bajo tu razonamiento determinas que debes informar a un humano de la situacion actual o esta presente en uno de los Motivos Validos"
    "El system Prompt contiene una lista de Motivos VALIDOS para crear una escalacion de este tipo, si la solicitud o sitacion actual no esta presente en alguno de estos Motivos, el Ticket NO DEBE SER CREADO."
    "Que un usuario quiera hablar o escalar la situacion con un humano NO es un motivo valido para usar esta herramienta, si el usuario solicita un humano, primero, entiende que es lo que requiere el usuario y luego actua conforme a esta necesidad y tus opciones."
    "Parametros a usar: email y phone(Como minino uno debe estar presente, si solo uno este presente el valor del dato faltante debe ser None, no incluyas strings u otra informacion si falta alguno de estos datos), name(Obligatorio):Nombre de referencia para la escalacion, package(Opcional):Numero de seguimiento o enterpriseCode del paquete description(Obligatoria): Descripcion del problema que requiere atencion humana."
    ))
    async def escalate_to_human(
    ctx:RunContextWrapper,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    description: str = "",
    name: str = "",
    package: Optional[str] = None) -> dict:
        print(f"🔝 Escalacion con Correo: {email or "No dado"}, telefono: {phone or "No dado"}, Descipcion: {description or "No dado"}, Nombre:{name or "No dado"}, Package:{package or "No dado"}")
        if not name:
            return{
                "status":"error",
                "message":"Por favor proporciona un nombre de Referencia para la escalacion, con esto podre proceder con la solicitud.",
                "next_step":"Solicita al usuario un nombre de Referencia para la escalacion."
                }
        if not email and not phone:
            return{
                "status":"error",
                "message":"Por favor proporciona un numero de Telefono o correo para poder proceder con la solicitud.",
                "next_step":"Solicita al usuario un numero de Telefono o correo validos para proceder con la solicitud"
                }
        if not description:
            return {
            "status":"error",
            "message":"Por favor proporciona una descripcion del Motivo de la escalacion con un Humano.",
            "next_step":"Solicita al usuarioel motivo para proceder con la solicitud"     
            }
        if package:
            package_id = await get_id_package(pool, package)
            if not package_id:
                return {
                        "status": "error",
                        "message": f"Paquete {package} no encontrado en la base de datos. Estas seguro es el paquete correcto?",
                        "next_step":"Informa al Usuario del error inmediatamente"
                        }
        try:
            ticket_info=escalate_to_zoho(email,phone,name,package,description)
            if ticket_info.get("status") == "error" :
                return {
                    "status":"error",
                    "message":"La escalacion no pudo ser posible, te recomiendo contactes directamente a nuestro departamento de servicio al cliente",
                    "next_step":"Informa al usuario que ocurrio un error al escalar la situacion, y direcciona al usuario a utilizar nuestros canales de contacto"
                }
            else:
                ticketNumber=ticket_info.get("ticket_number")
                DevURL=ticket_info.get("webUrl","Desconocido")
                if ctx.context.issued_tickets_info is None:
                    ctx.context.issued_tickets_info = []
                ctx.context.issued_tickets_info.insert(0,{"TicketNumber":ticketNumber,"DevURL":DevURL})
                return {
                    "status":"success",
                    "TicketNumber":ticketNumber,
                    "message":"Ticket creado exitosamente", 
                }
        except Exception as e:
            print(f"[Debug]--Eror al crear el ticket: {e}--[Debug]")
            return{
                "status": "error",
                "message": "No se ha podido crear el Ticket para la escalacion, Lamento los incovenientes, recomiendo contactar a nuestra Central Telefonica.",
                "next_step":"Informa al Usuario del error inmediatamente"            
            } 
    return escalate_to_human