from dotenv import load_dotenv
import os
import requests


load_dotenv()
import time

zoho_refresh_token=os.environ.get("Zoho_Refresh_Token", "")
zoho_org_id = "716348510"
zoho_client_id = os.environ.get("Zoho_Client_ID", "")
zoho_client_secret = os.environ.get("Zoho_Client_Secret", "")
zoho_org= os.environ.get("Zoho_Organization_ID")

##---------------------------------Auxiliares------------------------------------##
def upload_attachments_to_ticket(ticket_id: str, images: list[bytes]) -> list[dict]:
    """
    Sube una lista de imágenes (como bytes) como adjuntos al ticket de Zoho Desk.

    Parámetros:
      - ticket_id: ID del ticket ya creado.
      - images: lista de blobs (bytes) de las imágenes.

    Retorna:
      - Lista de resultados por imagen.
    """
    results = []
    token = get_cached_token()

    for i, img_bytes in enumerate(images):
        files = {
            "file": (f"image_{i+1}.jpg", img_bytes, "image/jpeg")
        }

        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "orgId": zoho_org_id
        }

        url = f"https://desk.zoho.com/api/v1/tickets/{ticket_id}/attachments"

        try:
            resp = requests.post(url, headers=headers, files=files)
            if resp.status_code == 201:
                data = resp.json()
                results.append({"status": "ok", "attachment_id": data.get("id")})
                print(f"✅ Imagen {i+1} subida correctamente")
                print(f"Respuesta {resp}")
            else:
                print(f"❌ Error subiendo imagen {i+1}: {resp.status_code}")
                print(f"Error: {resp.json()}")
                results.append({"status": "error", "code": resp.status_code})
        except Exception as e:
            print(f"⚠️ Excepción subiendo imagen {i+1}: {e}")
            results.append({"status": "error", "exception": str(e)})

    return results

##----------------------------Zoho--------------------------------##
_token_info = {
    "access_token": None,
    "expires_at": 0,
    "refresh_token": zoho_refresh_token,
}
def get_cached_token():
    if _token_info["access_token"] and time.time() < _token_info["expires_at"]:
        return _token_info["access_token"]
    else:
        token = refresh_token()
        return token

def refresh_token():
    client_id = zoho_client_id
    client_secret = zoho_client_secret
    refresh_token = _token_info["refresh_token"]

    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token"
    }

    response = requests.post(url, params=params)
    data = response.json()

    _token_info["access_token"] = data["access_token"]
    _token_info["expires_at"] = time.time() + int(data["expires_in"]) - 60 
    return _token_info["access_token"]

def get_zoho_contact(email: str = "", phone: str = "", token: str = "") -> dict:
    url = "https://desk.zoho.com/api/v1/contacts/search"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "orgId": zoho_org_id,
    }

    def buscar_contacto(param_type: str, value: str) -> dict:
        params = {param_type: value}
        print(f"🔍 Buscando por {param_type}: {value}")
        resp = requests.get(url, headers=headers, params=params)
        print(f"🔁 Código respuesta: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json().get("data", [])
                if data:
                    print(f"✅ Contacto encontrado por {param_type}")
                    return data[0]
            except Exception as e:
                return {
                    "error": f"Error al decodificar JSON ({param_type})",
                    "details": str(e),
                    "raw_response": resp.text
                }
        return {}
    contacto = {}
    if phone:
        contacto = buscar_contacto("phone", phone)
    if not contacto and email:
        contacto = buscar_contacto("email", email)

    if not contacto:
        return { "response": "No contacts found" }

    return contacto

def create_zoho_contact(email: str, phone: str, name: str, token:str) -> dict:
    """
    Crea un nuevo contacto en Zoho Desk.

    Parámetros:
      - email: correo del contacto.
      - phone: teléfono del contacto.
      - name: nombre del contacto.

    Retorna:
      - Diccionario con los datos del contacto creado o error.
    """
    url = "https://desk.zoho.com/api/v1/contacts"

    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "orgId": zoho_org_id,
        "Content-Type": "application/json"
    }

    payload = {
        "lastName": name or "Cliente",
        "email": email,
        "phone": phone
    }
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        return response.json()
    else:
        try:
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.json()
            }
        except Exception:
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text
            }

##----------------------------Tools--------------------------------##
def create_pickup_ticket(email: str, phone: str,
                         name: str, package_id: str,
                         description: str = "") -> dict:
    """
    Crea un ticket en Zoho Desk usando los datos provistos.

    Parámetros:
      - email: correo del contacto.
      - phone: teléfono del contacto.
      - name: nombre del contacto.
      - package_id: identificador del paquete.
      - description: descripción opcional del ticket.

    Retorna:
      - Diccionario JSON con lo retornado por Zoho (el ticket creado).
    """
    print(f"🛠️ Creando ticket de recogida para {package_id}... \n Tipo de dato: {type(package_id)}")
    try:
        token = get_cached_token()
        contact = get_zoho_contact(email=email, phone=phone, token=token)     
        if "id" not in contact:
            print("⚠️ No se encontró contacto, creando uno nuevo...")
            contact = create_zoho_contact(email=email,phone=phone, name=name, token=token)
            if "id" not in contact:
                return {
                    "error": "No se pudo crear el contacto",
                    "details": contact
                }
                
                
        url = "https://desk.zoho.com/api/v1/tickets"

        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "orgId": zoho_org_id,
            "Content-Type": "application/json"
        }

        payload = {
            "subject": "Retiro en sede (Prueba de Integración)",
            "email": email,
            "phone": phone,
            "description":"ESTO ES UNA PRUEBA, por favor hacer caso omiso.\n\n"+ description,
            "departmentId": "504200000001777045",
            "channel": "WhatsApp",
            "teamId": "504200000035799001",
            "cf": {
                "cf_id_de_envio": package_id
            },
            "status" : "Closed",
            "contactId": contact["id"]
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        ticket_data = response.json()
        ticket_number = ticket_data.get("ticketNumber", "DESCONOCIDO")
        
        print(f"🎫 Ticket creado: {ticket_number}")
        
        return {
            "ticket_number": ticket_number,
            "message": "Ticket creado exitosamente"
        }
    except Exception as e:
        return {
            "error": "Error general al crear ticket",
            "details": str(e)
        }   
        
def request_electronic_receipt(owner: dict, package_id: str,legal_name:str, legal_id: str,            
                            full_address: str, reason: str = "") -> dict:
    """
    Crea un ticket en Zoho Desk usando los datos provistos.

    Parámetros:
      - email: correo del contacto.
      - phone: teléfono del contacto.
      - name: nombre del contacto.
      - package_id: identificador del paquete.
      - description: descripción opcional del ticket.

    Retorna:
      - Diccionario JSON con lo retornado por Zoho (el ticket creado).
    """
    email = owner.get("email", None)
    phone = owner.get("phone", None)
    name = owner.get("name",None)
    
    try:
        token = get_cached_token()
        contact = get_zoho_contact(email=email, phone=phone, token=token)
        
        if "id" not in contact:
            print("⚠️ No se encontró contacto, creando uno nuevo...")
            contact = create_zoho_contact(email=email,phone=phone, name=name, token=token)
            if "id" not in contact:
                return {
                    "error": "No se pudo crear el contacto",
                    "details": contact
                }
                
                
        url = "https://desk.zoho.com/api/v1/tickets"

        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "orgId": zoho_org_id,
            "Content-Type": "application/json"
        }

        payload = {
            "subject": "Solicitud Factura Electronica (Prueba de Integración)",
            "email": email,
            "phone": phone,
            "description":
                f"ESTO ES UNA PRUEBA, por favor hacer caso omiso.\n\n Descripcion: {reason}\n"
                f"Nombre Juridico: {legal_name} \n"
                f"Cedula Juridica: {legal_id} \n"
                f"Direccion Completa: {full_address} \n",          
            "departmentId": "504200000001777045",
            "channel": "WhatsApp",
            "teamId": "504200000035799001",
            "cf": {
                "cf_id_de_envio": package_id
            },
            "status" : "Closed",
            "contactId": contact["id"]
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        ticket_data = response.json()
        ticket_number = ticket_data.get("ticketNumber", "DESCONOCIDO")
        
        print(f"🎫 Ticket creado: {ticket_number}")
        
        return {
            "ticket_number": ticket_number,
            "message": "Ticket creado exitosamente"
        }
    except Exception as e:
        return {
            "error": "Error general al crear ticket",
            "details": str(e)
        }    
        
def report_package_damaged(owner: dict, package_id: str, description: str, img_data: list[int] = []) -> dict:
    """
    Crea un ticket en Zoho Desk para reportar un paquete dañado.

    Parámetros:
      - owner: diccionario con datos del propietario del paquete.
      - package_id: identificador del paquete.
      - description: descripción del daño.
      - img_data: lista de IDs de imágenes relacionadas al daño.

    Retorna:
      - Diccionario JSON con lo retornado por Zoho (el ticket creado).
    """
    email = owner.get("email", None)
    phone = owner.get("phone", None)
    name = owner.get("name", None)

    try:
        token = get_cached_token()
        contact = get_zoho_contact(email=email, phone=phone, token=token)
        
        if "id" not in contact:
            print("⚠️ No se encontró contacto, creando uno nuevo...")
            contact = create_zoho_contact(email=email, phone=phone, name=name, token=token)
            if "id" not in contact:
                return {
                    "error": "No se pudo crear el contacto",
                    "details": contact
                }
                
        url = "https://desk.zoho.com/api/v1/tickets"

        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "orgId": zoho_org_id,
            "Content-Type": "application/json"
        }

        payload = {
            "subject": f"Reporte de Paquete Dañado - {package_id}  (Prueba de Integración)",
            "email": email,
            "phone": phone,
            "description": f"ESTO ES UNA PRUEBA, por favor hacer caso omiso.\n\n Descripción del daño: {description}",
            "departmentId": "504200000001777045",
            "channel": "WhatsApp",
            "teamId": "504200000035799001",
            "cf": {
                "cf_id_de_envio": package_id
            },
            "status" : "Closed",
            "contactId": contact["id"]
        }

        response = requests.post(url, headers=headers, json=payload)
        
        if not response.ok:
            return {
                "status": "error",
                "message": f"Error al crear el ticket: {response}"
            }
        
        ticket_data = response.json()
        ticket_id= ticket_data.get("id", "DESCONOCIDO")
        ticketNumber=ticket_data.get("ticketNumber","DESCONOCIDO")
        
        attachment_results = []
        if img_data:
            print(f"📤 Subiendo {len(img_data)} imágenes al ticket {ticket_id}...")
            attachment_results = upload_attachments_to_ticket(ticket_id, img_data)
            
        return {
            "status": "ok",
            "message": f"Ticket de daño creado para el paquete {package_id}",
            "Numero de Ticket": ticketNumber,
            "attachments": attachment_results
        } 
        
    except Exception as e: 
        return {
            "status": "error",
            "message": f"Error general al crear ticket: {str(e)}"
        }
        