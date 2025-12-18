from agents import function_tool, RunContextWrapper
from handlers.db_handlers import get_id_package,get_package_historic
from handlers.aux_handlers import create_pickup_ticket,request_electronic_receipt,_parse_date_cr,report_package_damaged
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

DELIVERED_STATES= {"DELIVERED", "DELIVEREDCOMPLETE"}
RETURN_STATES= {"RETURN"}
FAILED_STATES= {"FAILED","DELETEPACKAGE","CANCELNOCHARGE","CANCEL"}

CR_TZ = ZoneInfo("America/Costa_Rica")

def Make_get_package_timeline_tool(pool):
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
        print(f"✅ Ticket de factura electronica creado: {response}") 
        return response

    return pickup_instore_ticket

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
            new_ticket = {"TicketNumber": ticketNumber, "DevURL": DevURL}
            
            response ={
                "status":"success",
                "TicketNumber":ticketNumber,
                "message":"Ticket creado exitosamente",
            }
            print(f"✅ Ticket de factura electronica creado: {response}")
            return response
        except Exception as e:
            print(f"⚠️ Error al crear ticket para factura electronica")
            return {
                    "status":"error",
                    "message":"Ocurrio un error al crear el ticket",
                    "next_step":"Informa al usuario del error inmediatamente."
                    }

    return request_electronic_receipt_ticket

def Make_package_damaged_tool(tools_pool):
    @function_tool(
        name_override="package_damaged_ticket",
        description_override="Crea un ticket para reportar el daño de un paquete a partir de su Tracking o número de seguimiento. Solo procede si el último estado del paquete es DELIVERED y han pasado más de 48 horas desde esa entrega. Requiere número de seguimiento, descripción del daño y fotos."
    )
    async def package_damaged_ticket(
        package: str,
        description: str
    ) -> dict:
        print(f"🔨 Intentando crear ticket para paquete dañado. Tracking: {package} | Desc: {description}")

        if not package or not description:
            return {
                "status": "error",
                "message": "Faltan datos para crear el ticket.Tracking y descripción del daño deben ser proporcionados.",
                "next_step":" Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario."                    
                }

        package_id = await get_id_package(tools_pool, package)
        if not package_id:
            return {
                    "status": "error", 
                    "message": f"Paquete {package} no encontrado en la base de datos.",
                    "next_step":" Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario." 
                    }

        package_historic = await get_package_historic(tools_pool, package_id)
        timeline = package_historic.get("timeline", []) or []
        if not timeline:
            return {
                "status": "error", 
                "tracking": str(package_id),
                "package_found": True,
                "message": "No hay historial de estados para este paquete.",
                "next_step":" Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario." 
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
                "next_step":" Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario." 
            }
            
        if not last_dt:
            return {
                "status":"error",
                "tracking": str(package_id),
                "package_found": True,
                "message": "No se pudo validar la fecha de entrega del paquete.",
                "next_step":" Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario." 
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
                "next_step":" Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario." 
            }

        owner_info = {
            "email": package_historic.get("email_dueño_paquete", "") or package_historic.get("email_duenho_paquete", ""),
            "phone": package_historic.get("telefono_dueño", "") or package_historic.get("telefono_dueño_paquete", ""),
            "name":  package_historic.get("nombre_dueño_paquete", "") or package_historic.get("nombre_duenho_paquete", "")
        }

        result = report_package_damaged(
            owner=owner_info,
            package_id=str(package_id),
            description=description,
        )

        if result.get("status") == "ok":
            print("✅ Ticket creado con éxito")
            ticketNumber=result.get("Numero de Ticket")
            DevURL=result.get("webUrl","Desconocido")
            
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
                "next_step":" Informa al agente del error inmediatamente y aconseja confirmar la informacion con el usuario." 
            }

    return package_damaged_ticket