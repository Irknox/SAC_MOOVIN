from fastapi import FastAPI, Body, HTTPException, Header, Request
from typing import Dict, Any
from handlers.aux_handlers import translate_to_spanish,get_time
from handlers.db_handlers import create_mysql_pool, create_tools_pool,save_to_mongodb,get_user_env
from tools.api_tools import Make_get_package_timeline_tool,Make_request_to_pickup_tool,Make_request_electronic_receipt_tool, Make_package_damaged_tool,Make_escalate_call_tool,Make_remember_call_history_tool
import os
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
import hmac
import hashlib
import json
from datetime import datetime
import pymongo
import re

admins_phones= {
    "9999": os.environ.get("PHONE_EXT_9999",""),
    "5555": os.environ.get("PHONE_EXT_5555",""),
    "9090": os.environ.get("PHONE_EXT_9090","")
}
@asynccontextmanager
async def lifespan(app: FastAPI):
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    app.state.mongo_client = pymongo.MongoClient(MONGO_URI)
    app.state.calls_collection = app.state.mongo_client["moovin_calls"]["summaries"]  
    app.state.db_pool = await create_mysql_pool()
    app.state.tools_pool = await create_tools_pool()
    app.state.tools = {
        "check_package_status": Make_get_package_timeline_tool(app.state.tools_pool),
        "pickup_in_store": Make_request_to_pickup_tool(app.state.tools_pool),
        "electronic_receipt": Make_request_electronic_receipt_tool(app.state.tools_pool),
        "report_package_damaged": Make_package_damaged_tool(app.state.tools_pool),
        "escalate_call": Make_escalate_call_tool(),
        "remember_last_interactions": Make_remember_call_history_tool(app.state.calls_collection),
    }
    yield
    app.state.db_pool.close()
    await app.state.db_pool.wait_closed()
    app.state.mongo_client.close() 
app = FastAPI(lifespan=lifespan)

Token_API=os.environ.get('SILVERAI_API_TOKEN')
@app.post("/SilverAPI")
async def silver_brain_endpoint(
    payload: Dict[str, Any] = Body(...),
    auth_token: Optional[str] = Header(None, alias="auth_token")

):
    """

    Endpoint para procesar solicitudes al SilverBrain.

    """
    if auth_token != Token_API:
        print(f"Intento de acceso no autorizado con token: {auth_token}")
        raise HTTPException(status_code=401, detail="No autorizado: Token inválido")
    try:
        tool_requested = payload.get("request")
        params = payload.get("params", {})
        if tool_requested in app.state.tools:
            selected_tool = app.state.tools[tool_requested]
            if tool_requested == "check_package_status":
                result = await selected_tool(
                    package_id=params.get("package"), 
                    phone=params.get("phone")
                )
            elif tool_requested == "pickup_in_store":
                result = await selected_tool(
                    package=params.get("package"),
                    description=params.get("description")
                )
            elif tool_requested == "electronic_receipt":
                result = await selected_tool(
                    package=params.get("package"),
                    reason=params.get("reason"),
                    legal_name=params.get("legal_name"),
                    legal_id=params.get("legal_id"),
                    full_address=params.get("full_address"),
                )
            elif tool_requested == "report_package_damaged":
                result = await selected_tool(
                    package=params.get("package"),
                    description=params.get("description")
                )
            elif tool_requested == "escalate_call":
                result = await selected_tool(
                    user_phone=params.get("user_phone"),
                    channel=params.get("channel")
                )
            elif tool_requested == "remember_call_history":
                result = await selected_tool(
                    phone=params.get("phone")
                )
            return {"status": "success", "data": result}

        return {"status": "error", "message": "Herramienta no encontrada"}
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

##==========================Endpoint para Webhook de Eleven Labs==========================##
WEBHOOK_SECRET = os.environ.get("ELEVENLABS_WEBHOOK_SECRET_TESTING")
@app.post("/webhooks/elevenlabs-post-call")
async def elevenlabs_post_call_webhook(request: Request):
    payload_raw = await request.body()
    signature_header = request.headers.get("elevenlabs-signature") 
    if not signature_header:
        print("🔴 Webhook recibido sin firma")
        raise HTTPException(status_code=401, detail="Missing signature")
    try:
        parts = dict(x.split('=') for x in signature_header.split(','))
        timestamp = parts.get('t')
        received_hash = parts.get('v0')
        signed_payload = f"{timestamp}.{payload_raw.decode('utf-8')}"
        
        expected_hash = hmac.new(
            WEBHOOK_SECRET.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(received_hash, expected_hash):
            print("❌ Firma de Webhook inválida")
            raise HTTPException(status_code=401, detail="Invalid signature")
    except Exception as e:
        print(f"⚠️ Error al validar firma: {e}")
        raise HTTPException(status_code=401, detail="Signature validation failed")
    payload = json.loads(payload_raw)
    event_type = payload.get("type")
    data = payload.get("data", {})
    if event_type == "post_call_transcription":
        analysis = data.get("analysis", {})
        summary_en = analysis.get("transcript_summary", "")
        dynamic_vars = data.get("conversation_initiation_client_data", {}).get("dynamic_variables", {})
        caller_id = dynamic_vars.get("system__caller_id", "Unknown")
        event_time = payload.get("event_timestamp") 
        summary_es = await translate_to_spanish(summary_en) if summary_en else "Sin resumen"
        save_to_mongodb(
            collection=app.state.calls_collection,
            phone=caller_id,
            event_timestamp=event_time,
            summary_es=summary_es
        )

        print(f"📝 Proceso completado para {caller_id}")
    return {"status": "received"}

@app.post("/webhooks/elevenlabs-pre-call")
async def elevenlabs_pre_call_webhook(
        request: Request,    
        auth_token: Optional[str] = Header(None, alias="auth_token")
    ):
    if auth_token != Token_API:
        print(f"Intento de acceso no autorizado con token: {auth_token}")
        raise HTTPException(status_code=401, detail="No autorizado: Token inválido")
    payload = await request.json()
    print(f"📲 Webhook pre-llamada recibido: {payload}")
    current_time= await get_time()
    caller_id = payload.get("caller_id", "")
    phone_calling = admins_phones.get(caller_id, caller_id)
    username = ""
    info_paquetes_str = "No hay paquetes registrados recientemente."
    if caller_id:
        try:
            env_data = await get_user_env(app.state.tools_pool, phone_calling)
            if env_data:
                raw_name = env_data.get("username", "")
                if raw_name:
                    username = raw_name.strip().split()[0].title() + " "
            paquetes = env_data.get("paquetes", [])
            if isinstance(paquetes, list) and len(paquetes) > 0:
                lineas = [f"- {p['paquete']}: {p['estado']} ({p['fecha']})" for p in paquetes]
                info_paquetes_str = "Tus paquetes actuales son:\n" + "\n".join(lineas)
            elif isinstance(paquetes, str):
                info_paquetes_str = paquetes 
        except Exception as e:
            print(f"❌ Error consultando DB: {e}")
    return {
        "type": "conversation_initiation_client_data",
        "dynamic_variables": {
            "user_name": username,
            "phone_calling": phone_calling,
            "last_packages_info": info_paquetes_str,
            "current_time": current_time 
        },
        "conversation_config_override": {
            "agent": {
                "first_message": f"Hola {username}, soy Silver de Moovin! ¿Cómo puedo ayudarte hoy?"
            }
        }
    } 