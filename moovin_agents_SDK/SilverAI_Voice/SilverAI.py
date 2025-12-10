from flask import Flask, request, Response
from openai import OpenAI, InvalidWebhookSignatureError
import asyncio
import json
import os
import threading
from agents.realtime import RealtimeAgent, RealtimeRunner
from agents.realtime.openai_realtime import OpenAIRealtimeSIPModel
from websockets.exceptions import ConnectionClosedError
import requests
from tools import escalate_call
from datetime import datetime
from handlers.aux_handlers import resume_interaction
from handlers.db_handlers import (
    save_to_mongodb, 
    save_call_meta, 
    interaction_key, 
    append_interaction, 
    redis_key, 
    get_session_data, 
    delete_session_data
)
import pymongo

MONGO_URI = os.environ.get("MONGO_URI") 
MONGO_DATABASE = os.environ.get("MONGO_DATABASE") 
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION")

try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_client.admin.command('ping') 
    db = mongo_client[MONGO_DATABASE]
    sessions_collection = db[MONGO_COLLECTION]
    print(f"[INFO] Conexión a MongoDB exitosa. URI: {MONGO_URI}, Colección: {MONGO_COLLECTION}")
except Exception as e:
    print(f"[ERROR] No se pudo conectar a MongoDB. La persistencia fallará: {e}")
    mongo_client = None
    sessions_collection = None
    
app = Flask(__name__)

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    webhook_secret=os.environ["OPENAI_WEBHOOK_KEY"],
)     
    
AUTH_HEADER = {
    "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY"),
}

call_accept = {
    "type": "realtime",
    "instructions": (
        "Eres un Agente de Servicio al Cliente para la compañía de logística y envíos Moovin "
        "(pronunciado 'Muvin')."
        "Habla en español latino, manten un tono natural, sin acentos."
    ),
    "model": "gpt-4o-realtime-preview",
}


async def run_realtime_session(call_id: str):
    """Engancha un RealtimeAgent (SDK) a la llamada SIP usando el call_id
    que llega por el webhook realtime.call.incoming.
    """
    
    voice_agent = RealtimeAgent(
        name="Silver",
        instructions=(
            "Eres un Agente de Servicio al Cliente para la compañía de logística y envíos Moovin "
            "(pronunciado 'Muvin'). "
            "Respondes con voz natural, en español latino, de forma clara y concisa. "
            "Si el usuario no entiende algo, reformula con otras palabras."
            
            "Cuentas con una herramienta llamada escalate_call, con esta herramienta transfieres la llamada a un agente humano."
        ),
        tools=[escalate_call]
    )

    runner = RealtimeRunner(
        starting_agent=voice_agent,
        model=OpenAIRealtimeSIPModel(),
    )
    
    current_interaction = {
        "user": None, 
        "steps_taken": [], 
        "agent": None,
        "date": datetime.now().isoformat(), 
        }
    
    tool_calls_pending = {}
    def finalize_and_save_interaction():
        """Consolida el current_interaction y lo añade a la lista de Redis."""
        nonlocal current_interaction
        if current_interaction["user"] or current_interaction["agent"] or current_interaction["steps_taken"]:
            append_interaction(call_id, current_interaction)
        
        current_interaction = {
            "user": None, 
            "steps_taken": [], 
            "agent": None,
            "date": datetime.now().isoformat(),
        }
    model_config = {
        "call_id": call_id,
        "initial_model_settings": {
            "modalities": ["audio"],
            "voice": "ash",
            "speed": 1.3,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "gpt-4o-mini-transcribe",
            },
            "input_audio_noise_reduction": {
                "type": "near_field",
            },
            "turn_detection": {
                "type": "server_vad",
                "interrupt_response": True,
                "threshold": 0.8,
            },
        },
    }
    try:
        ctx = {
        "call_id": call_id,
        }
    
        async with await runner.run(context=ctx,model_config=model_config) as session:
            initial_message = "Hola, soy Silver, asistente virtual de Moovin (pronunciado Muvin), ¿cómo puedo asistirte hoy?"
            await session.send_message(
                f"Dile al usuario: '{initial_message}'"
            )
            current_interaction["agent"] = {
                "text": initial_message,
                "date": datetime.now().isoformat(),
            }
            finalize_and_save_interaction()
            async for event in session:
                print(f"Realtime event: {event.type}")
                
                if event.type == "realtime.transcription.completed":
                    if current_interaction["user"] or current_interaction["agent"]:
                         finalize_and_save_interaction()
                    current_interaction["user"] = {
                        "text": event.data.text,
                        "date": datetime.now().isoformat(),
                    }
                elif event.type == "realtime.agent.response.completed":
                    current_interaction["agent"] = {
                        "text": event.data.text,
                        "date": datetime.now().isoformat(),
                    }
                    finalize_and_save_interaction()
                elif event.type == "function.call.created":
                    tool_call_id = event.data.tool_call_id
                    
                    tool_calls_pending[tool_call_id] = {
                        "type": "tool_call",
                        "tool_name": event.data.tool_name,
                        "arguments": event.data.arguments,
                        "date_started": datetime.now().isoformat(),
                    }
                    current_interaction["steps_taken"].append(tool_calls_pending[tool_call_id])
                elif event.type == "function.call.completed":
                    tool_call_id = event.data.tool_call_id
                    
                    if tool_call_id in tool_calls_pending:
                        tool_entry = tool_calls_pending[tool_call_id]
                        tool_entry["date_completed"] = datetime.now().isoformat()
                        tool_entry["output"] = event.data.output
                        tool_entry["status"] = "completed"
                        
                        del tool_calls_pending[tool_call_id]
    
    except ConnectionClosedError as e:
        print(f"[ERROR-NETWORK] Sesión Realtime cerrada abruptamente (WebSocket/RTP) para call_id={call_id}: {type(e).__name__}: {str(e)}")
        
    except Exception as e:
        print(f"[ERROR-SESSION] Sesión Realtime fallida para call_id={call_id}: {type(e).__name__}: {str(e)}")
        raise e 

    finally:
        finalize_and_save_interaction()
        meta_json, interactions_list = get_session_data(call_id)
        interacion_summary = await resume_interaction(interactions_list)
        full_session_data = None
        if meta_json:
            meta = json.loads(meta_json)
            meta["finish_date"] = datetime.now().isoformat()
            session_status = "ended_with_error" if 'e' in locals() else "ended_cleanly"
            meta["status"] = session_status
            meta["summary"] = interacion_summary
            save_call_meta(call_id, meta) 
            full_session_data = {**meta, "interactions": interactions_list}
            if full_session_data:
                save_to_mongodb(sessions_collection, full_session_data)
        if full_session_data:
            print(f"[DEBUG] Sesión Completa para Persistencia (call_id={call_id}):")
            print(f"  - Status Final: {full_session_data['status']}")
            print(f"  - Total Interacciones: {len(full_session_data['interactions'])}")
            
            if len(full_session_data['interactions']) > 0:
                 print(f"  - Primera Interacción: {json.dumps(full_session_data['interactions'][0])}")
        else:
            print(f"[DEBUG] No se encontró metadata en Redis para call_id={call_id} antes de limpiar.")
        delete_session_data(call_id)
        print(f"[DEBUG] Redis cleanup OK para call_id={call_id}")
        
        
        
def start_session_in_thread(call_id: str):
    """Wrapper para lanzar la sesión async del SDK en un thread."""
    asyncio.run(run_realtime_session(call_id))

@app.route("/", methods=["POST"])
def webhook():
    try:
        event = client.webhooks.unwrap(request.data, request.headers)
        if event.type == "realtime.call.incoming":
            call_id = event.data.call_id
            sip_headers = {}
            for h in (event.data.sip_headers or []):
                sip_headers[h.name] = h.value
            print(f"Incoming call: {call_id}, SIP headers: {sip_headers}")
            session_meta = {
                "session_id": call_id,
                "summary": None,
                "init_date": event.created_at, 
                "finish_date": None,
                "status": "incoming", 
                "user_info": { 
                    "phone_number": sip_headers.get("From", "Unknown"), 
                    "explication": "Se obtuvo el número del SIP header 'From'."
                },
                "meta_data": {         
                    "x_ast_uniqueid": sip_headers.get("X-Ast-UniqueID"),
                    "x_ast_channel": sip_headers.get("X-Ast-Channel"),
                    "sip_call_id": sip_headers.get("Call-ID"),
                    "sip_headers": sip_headers,
                },
            }
            
            save_call_meta(call_id, session_meta) 
            
            
            requests.post(
                f"https://api.openai.com/v1/realtime/calls/{call_id}/accept",
                headers={**AUTH_HEADER, "Content-Type": "application/json"},
                json=call_accept,
            )

            threading.Thread(
                target=start_session_in_thread,
                args=(call_id,),
                daemon=True,
            ).start()

        return Response(status=200)

    except InvalidWebhookSignatureError as e:
        print("Invalid signature", e)
        return Response("Invalid signature", status=400)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8585)
