import os
import json
import asyncio
from openai import AsyncOpenAI 

client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)
from dotenv import load_dotenv
import os
import requests
import time
from datetime import datetime
from zoneinfo import ZoneInfo

load_dotenv()

CR_TZ = ZoneInfo("America/Costa_Rica")

zoho_refresh_token=os.environ.get("Zoho_Refresh_Token", "")
zoho_org_id = "716348510"
zoho_client_id = os.environ.get("Zoho_Client_ID", "")
zoho_client_secret = os.environ.get("Zoho_Client_Secret", "")
zoho_org= os.environ.get("Zoho_Organization_ID")
moovin_url=os.environ.get("Moovin_URL")
ZOHOENDPOINT = "https://desk.zoho.com/api/v1/tickets"
Z_DEPARTMENT_ID = os.environ.get("Zoho_Department_ID")
Z_TEAM_ID = os.environ.get("Zoho_Team_ID")
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
    if response.status_code == 200:
        print (f"✅ Contacto creado")
        return response.json()
    else:
        print (f"❌ Error al crear el contacto")
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


async def resume_interaction(interactions: list) -> str:
    """
    Función que toma las interacciones cliente-agente, las pasa a un LLM que se 
    encarga de resumir la conversación antes de persistir los datos y cerrar la sesión.
    
    Args:
        interactions (list): Lista de objetos de interacción (turnos) recuperados de Redis.
        
    Returns:
        str: El resumen generado por el LLM, o un mensaje de error si falla.
    """
    
    transcript_lines = []
    
    for interaction in interactions:
        if interaction.get("user") and interaction["user"].get("text"):
            transcript_lines.append(f"USUARIO: {interaction['user']['text']}")
        
        if interaction.get("agent") and interaction["agent"].get("text"):
            transcript_lines.append(f"AGENTE: {interaction['agent']['text']}")
            
    full_transcript = "\n".join(transcript_lines)
    
    
    system_prompt = (
        "Eres un experto en resumir interacciones de un Agente de Soporte al Cliente y el usuario para una compañia de envios y logistica. "
        "Tu tarea es generar un resumen apartir de la transcripción completa de la conversación. "
        "Incluye el motivo de la llamada, las acciones tomadas y todo detalle de importancia en la interacción."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Por favor, resume la siguiente conversación:\n\n---\n\n{full_transcript}"}
    ]
    
    try:
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0,
        )
        
        summary = completion.choices[0].message.content.strip()
        print(f"[DEBUG] Resumen generado exitosamente")
        return summary
        
    except Exception as e:
        error_message = f"Error al generar resumen con LLM: {str(e)}"
        print(f"[ERROR] {error_message}")
        return f"ERROR: Fallo la generación del resumen. Detalle: {str(e)}"

##-----------------------Ticketing Helper Functions -----------------------##

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
        TicketURL=ticket_data.get("webUrl","No disponible")
        
        print(f"🎫 Ticket creado: {ticket_number}")
        
        return {
            "ticket_number": ticket_number,
            "message": "Ticket creado exitosamente",
            "webUrl":TicketURL
        }
    except Exception as e:
        return {
            "error": "Error general al crear ticket",
            "details": str(e)
        }   
 