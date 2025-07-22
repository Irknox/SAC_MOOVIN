from dotenv import load_dotenv
import os
import requests

load_dotenv()


refresh_token=os.environ.get("Zoho_Refresh_Token", "")
zoho_access_token = ""
zoho_org_id = "716348510"  # Replace with your actual Zoho organization ID
zoho_client_id = os.environ.get("Zoho_Client_ID", "")
zoho_client_secret = os.environ.get("Zoho_Client_Secret", "")
zoho_org= os.environ.get("Zoho_Organization_ID")


##----------------------------Zoho--------------------------------##

def get_zoho_access_token():
    global zoho_access_token
    if not zoho_access_token:
        url = "https://accounts.zoho.com/oauth/v2/token"
        params = {
            "refresh_token": refresh_token,
            "client_id": zoho_client_id,
            "client_secret": zoho_client_secret,
            "grant_type": "refresh_token"
        }
        response = requests.post(url, params=params)
        response.raise_for_status()
        zoho_access_token = response.json().get("access_token")
        print(f"Zoho response: {response.json()}")
    return zoho_access_token


def create_pickup_ticket(access_token: str,
                         email: str, phone: str,
                         name: str, package_id: str,
                         description: str = "") -> dict:
    """
    Crea un ticket en Zoho Desk usando los datos provistos.

    Parámetros:
      - access_token: token válido de Zoho.
      - org_id: ID de la organización (ej. "716348510").
      - email: correo del contacto.
      - phone: teléfono del contacto.
      - name: nombre del contacto.
      - package_id: identificador del paquete.
      - description: descripción opcional del ticket.

    Retorna:
      - Diccionario JSON con lo retornado por Zoho (el ticket creado).
    """
    access_token = get_zoho_access_token()
    url = "https://desk.zoho.com/api/v1/tickets"

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "orgId": zoho_org_id,
        "Content-Type": "application/json"
    }

    payload = {
        "subject": "ESTO ES UNA PRUEBA, por favor hacer caso omiso. Actualizar Datos de Entrega",
        "email": email,
        "phone": phone,
        "description": description+"\n\n ESTO ES UNA PRUEBA, por favor hacer caso omiso.",
        "departmentId": "504200000001777045",
        "layoutId": "504200000037719616",
        "channel": "WhatsApp",
        "teamId": "504200000035799001",
        "cf": {
            "cf_id_del_envio": package_id
        },
        "status" : "Closed",
        "statusType": "Closed"
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()