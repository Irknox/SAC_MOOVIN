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
import redis
from tools import escalate_call

REDIS_URL = os.environ["REDIS_URL"]

rdb = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)

def redis_key(call_id: str) -> str:
    return f"calls:{call_id}"

def save_call_meta(call_id: str, meta: dict, ttl_seconds: int = 3600) -> None:
    rdb.set(redis_key(call_id), json.dumps(meta), ex=ttl_seconds)

def delete_call_meta(call_id: str) -> None:
    rdb.delete(redis_key(call_id))

app = Flask(__name__)

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    webhook_secret=os.environ["OPENAI_WEBHOOK_KEY"],
)  


voice_agent = RealtimeAgent(
    name="Silver",
    instructions=(
        "Eres un Agente de Servicio al Cliente para la compañía de logística y envíos Moovin "
        "(pronunciado 'Muvin'). "
        "Respondes con voz natural, en español latino, de forma clara y concisa. "
        "Si el usuario no entiende algo, reformula con otras palabras."
    ),
    tools=[escalate_call]
)

runner = RealtimeRunner(
    starting_agent=voice_agent,
    model=OpenAIRealtimeSIPModel(),
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
        
        async with await runner.run(model_config=model_config) as session:
            await session.send_message(
                "Dile al usuario: 'Mi nombre es Silver, asistente virtual de Moovin "
                "(pronunciado Muvin), ¿cómo puedo asistirte hoy?'"
            )

            async for event in session:
                print("Realtime event:", event)
    except ConnectionClosedError:
        print("Sesión Realtime finalizada: cierre de WebSocket (fin de llamada SIP).")

    except Exception as e:
        print("Error en sesión Realtime:", repr(e))
    finally:
        delete_call_meta(call_id)
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

            meta = {
                "call_id": call_id,
                "sip_headers": sip_headers,
                "x_ast_uniqueid": sip_headers.get("X-Ast-UniqueID"),
                "x_ast_channel": sip_headers.get("X-Ast-Channel"),
                "sip_call_id": sip_headers.get("Call-ID"),
                "created_at": event.created_at,
                "status": "incoming",
            }
            save_call_meta(call_id, meta)
            
            
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
