from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal
import os
import tempfile
import requests
from handlers.main_handler import get_msgs_from_last_states, save_message, get_user_env, get_users_last_messages, get_last_messages_by_user, save_img_data, reverse_geocode_osm
from config import create_mysql_pool, create_tools_pool
from main import build_agents, MoovinAgentContext
from agents import (Runner, MessageOutputItem, HandoffOutputItem, InputGuardrailTripwireTriggered,RunContextWrapper,OutputGuardrailTripwireTriggered)
import json
from datetime import datetime, timedelta, timezone
import traceback
import base64
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv
from collections import OrderedDict
import asyncio
import redis.asyncio as redis
from handlers.redis_handler import RedisSession, SESSION_IDLE_SECONDS

image_buffer: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
location_buffer: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

load_dotenv()


client = OpenAI()

##----------------------------Funciones Auxiliares----------------------------##
def save_base64_audio(base64_string: str, suffix: str = ".ogg") -> str:
    """
    Guarda el audio base64 como archivo binario (.ogg por defecto).
    Devuelve la ruta del archivo guardado.
    """
    audio_bytes = base64.b64decode(base64_string)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    with open(temp_file.name, 'wb') as f:
        f.write(audio_bytes)
    return temp_file.name
    
async def transcribe_audio(media_key_b64: str) -> str:
    decrypted_path = save_base64_audio(media_key_b64)
    print(f"📥 Audio cifrado guardado en: {decrypted_path}")
    if not decrypted_path:
        return "[Error al descifrar audio]"
    print(f"📥 Audio descifrado guardado en: {decrypted_path}")

    try:
        with open(decrypted_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es"
            )
        return transcript.text
    except Exception as e:
        print("❌ Error al transcribir:", e)
        return "[Error al transcribir audio]"

async def build_state(request: Request, user_id: str, user_name: str, user_message: str, img_data_ids: list[int], location_data: dict |  None) -> dict:
    redis_session=request.app.state.redis_session
    user_buffer_memory=await redis_session.get_session(user_id)
    if not user_buffer_memory:
        print (f"🆕 Usuario no tiene session activa, creando nueva sesion")
        ctx = request.app.state.create_initial_context()
        ctx.user_id = user_id
        ctx.imgs_ids= img_data_ids or []
        ctx.location_sent = location_data or {}
        user_env_data = await get_user_env(request.app.state.tools_pool, user_id, whatsapp_username=user_name)
        ctx.user_env = user_env_data
        state = {
                "context": ctx,
                "input_items": [],
                "current_agent": request.app.state.agents["General Agent"].name,
            }
    else:
        state=user_buffer_memory.get("state")  
        try:
            raw_context = state.get("context")
            restored_context = MoovinAgentContext(**raw_context)
            user_env_data = await get_user_env(request.app.state.tools_pool, user_id, whatsapp_username=user_name)
            restored_context.user_env = user_env_data
            if img_data_ids:
                restored_context.imgs_ids = img_data_ids
            restored_context.location_sent=location_data or {}
            state = {
                "context": restored_context,
                "input_items": state.get("input_items", []),
                "current_agent": state.get("current_agent", request.app.state.agents["General Agent"].name),
            }
        except Exception as e:
            print("⚠️ Error restaurando contexto desde BD, se crea uno nuevo:", e)
            ctx = request.app.state.create_initial_context()
            ctx.user_id = user_id
            user_env_data = await get_user_env(request.app.state.tools_pool, user_id, whatsapp_username=user_name)
            ctx.user_env = user_env_data
            state = {
                    "context": ctx,
                    "input_items": [],
                    "current_agent": request.app.state.agents["General Agent"].name,
                }      
    return state

async def send_text_to_whatsapp(user_id: str, user_message: str, response_text: str, message_id: str):
    """
    Envía un mensaje de texto a un número de WhatsApp mediante Evolution API.
    """
    url = f"{os.environ.get('Whatsapp_URL')}/message/sendText/SAC-Moovin"
    payload = {
        "number": user_id.replace("@s.whatsapp.net", ""),
        "text": response_text,
        "delay": 100,
        "linkPreview": False,
        "mentionsEveryOne": False,
        "mentioned": [user_id],
        "quoted": {
            "key": {"id": message_id},
            "message": {"conversation": user_message}
        }
    }
    headers = {
        "apikey": os.environ.get("Whatsapp_API_KEY"),
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        print("📤 Enviado a WhatsApp ✔️")
        return response
    except Exception as e:
        print("❌ Error al enviar mensaje a WhatsApp:", e)
        return None

async def persist_session_to_mysql(mysql_pool, cid: str, session_obj: dict):
    import json

    state = session_obj.get("state", {}) or {}
    # Normaliza context si es Pydantic
    ctx = state.get("context")
    if hasattr(ctx, "model_dump"):
        state["context"] = ctx.model_dump()

    input_items = state.get("input_items", []) or []

    def extract_text_from_item(item: dict) -> str | None:
        """
        Devuelve el texto 'legible' del item. Soporta:
        - {"role":"user","content":"Hola"}
        - {"role":"assistant","content":[{"type":"output_text","text":"{\"response\":\"...\"}"}]}
        - {"role":"assistant","content":[{"type":"text","text":"..."}]}
        """
        content = item.get("content")
        if isinstance(content, str):
            return content.strip() or None
        if isinstance(content, list):
            for block in reversed(content):
                text = block.get("text")
                if not isinstance(text, str):
                    continue
                text = text.strip()
                if not text:
                    continue
                # A veces el modelo mete JSON con {"response":"..."}
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and "response" in parsed and isinstance(parsed["response"], str):
                        return parsed["response"].strip() or None
                except Exception:
                    pass
                return text 
        return None

    last_user_msg = None
    last_assistant_msg = None
    for it in reversed(input_items):
        role = it.get("role")
        if not last_assistant_msg and role == "assistant":
            last_assistant_msg = extract_text_from_item(it)
        if not last_user_msg and role == "user":
            last_user_msg = extract_text_from_item(it)
        if last_user_msg and last_assistant_msg:
            break

    user_message = last_user_msg or "[SESSION_FLUSH]"
    response_text = last_assistant_msg or "[BATCHED_SESSION]"

    await save_message(
        mysql_pool,
        cid,
        user_message,
        response_text,
        state
    )

async def session_flush_worker(app):
    redis_session: RedisSession = app.state.redis_session
    mysql_pool = app.state.mysql_pool
    while True:
        try:
            cids = await redis_session.due_sessions()
            for cid in cids:
                session_obj = await redis_session.get_session(cid)
                if not session_obj:
                    continue
                try:
                    await persist_session_to_mysql(mysql_pool, cid, session_obj)
                finally:
                    await redis_session.delete_session(cid)
        except Exception as e:
            print(f"[flush_worker] error: {e}")
        await asyncio.sleep(30)  # frecuencia de barrido


class AgentEvent(BaseModel):
    id: str
    type: Literal["handoff", "tool_call", "tool_output"]
    agent: str
    content: str

class MessageResponse(BaseModel):
    content: str
    agent: str

class GuardrailCheck(BaseModel):
    name: str = "Unnamed"
    passed: bool = True
    message: str = ""

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        mysql_pool = await create_mysql_pool()
        tools_pool = await create_tools_pool()

        general_agent, package_analysis_agent, mcp_agent, railing_agent ,create_initial_context = await build_agents(tools_pool,mysql_pool)
       
        
        app.state.mysql_pool = mysql_pool
        app.state.tools_pool = tools_pool
        app.state.agents = {
            mcp_agent.name: mcp_agent,
            general_agent.name: general_agent,
            package_analysis_agent.name: package_analysis_agent,
            railing_agent.name: railing_agent,
            
        }
        app.state.create_initial_context = create_initial_context

        
        REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

        app.state.redis = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=False
        )
        app.state.redis_session = RedisSession(app.state.redis)
        app.state._flush_task = asyncio.create_task(session_flush_worker(app))

        yield

        try:
            app.state._flush_task.cancel()
            await app.state._flush_task
        except Exception:
            pass

        mysql_pool.close()
        await mysql_pool.wait_closed()
        tools_pool.close()
        await tools_pool.wait_closed()
    except Exception as e:
        print("🔥 Error al iniciar FastAPI:", e)
        raise e
        

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str

class InMemoryStore:
    _store: Dict[str, Dict[str, Any]] = {}

    def get(self, cid: str) -> Optional[Dict[str, Any]]:
        return self._store.get(cid)

    def save(self, cid: str, state: Dict[str, Any]):
        self._store[cid] = state

store = InMemoryStore()

def _get_agent_by_name(app: FastAPI, name: str):
    return app.state.agents.get(name, app.state.agents["General Agent"])

def count_tokens(text, model="gpt-4o"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

@app.post("/ask")
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    try:
        data_item = payload["data"]
        message_data = data_item["message"]
        user_name = data_item.get("pushName", "Desconocido")
        user_id = data_item["key"]["remoteJid"]
        message_id = data_item["key"]["id"]
        
        img_data_ids= []
        
        ## ------------------------Procesamiento de mensajes de texto------------------------ ##
        if "conversation" in message_data:
            user_message = message_data["conversation"]

        ## ------------------------Procesamiento Ubicaciones------------------------ ##
        elif "locationMessage" in message_data:
            lat = message_data["locationMessage"]["degreesLatitude"]
            lng = message_data["locationMessage"]["degreesLongitude"]
            address_info_response = reverse_geocode_osm(lat, lng)
            direccion=address_info_response.get('display_name', None)
            user_message = f"[Ubicación recibida en formato de Ubicacion]"

            # Guardar ubicación en el buffer
            now = datetime.utcnow()
            if len(location_buffer) >= 30 and user_id not in location_buffer:
                location_buffer.popitem(last=False)  # Quitar el más viejo

            location_buffer[user_id] = {
                "location": {
                    "latitude": lat, 
                    "longitude": lng, 
                    "confirmations": {
                        "is_request_confirmed_by_user":False,
                        "is_new_address_confirmed":False
                        }
                },
                "last_seen": now,
                
            }

        ## ------------------------Procesamiento de audio------------------------ ##
        elif "audioMessage" in message_data:
            audio_b64 = message_data.get("base64")
            print(f"Audio en base64: {audio_b64}")
            if audio_b64:
                audio_transcripted = await transcribe_audio(audio_b64)
                user_message=audio_transcripted
            else:
                user_message = "[Audio recibido pero sin URL o mediaKey]"
                             
        ## ------------------------Procesamiento de imagenes------------------------ ##
        elif "imageMessage" in message_data:
            img_base64 = message_data.get("base64")
            img_info=message_data.get("imageMessage")
            caption = img_info.get("caption",None)
            if not img_base64:
                return {"status": "ok", "response": "[Imagen vacía ignorada]"}
            now = datetime.utcnow()

            if user_id in image_buffer:
                buffer = image_buffer[user_id]
                buffer["images"].append(img_base64)
                buffer["last_seen"] = now
                if len(buffer["images"]) > 5:
                    buffer["images"] = buffer["images"][-5:]
            else:
                if len(image_buffer) >= 30:
                    image_buffer.popitem(last=False)
                image_buffer[user_id] = {
                    "images": [img_base64],
                    "last_seen": now
                }
            await asyncio.sleep(5)
            last_seen = image_buffer[user_id]["last_seen"]
            if (datetime.utcnow() - last_seen).total_seconds() >= 5:
                num_imgs = len(image_buffer[user_id]["images"])
                if caption:
                    if  num_imgs == 1:
                        user_message = f"Mensaje del usuario: {caption} (Desde el sistema -> Ademas: Una imagen fue recibida del usuario.)"
                    else:
                        user_message=f"Mensaje del usuario: {caption} (Desde el sistema -> Ademas:{num_imgs} imágenes fueron recibidas del usuario.)"
                elif  num_imgs == 1:
                    user_message = "Imagen recibida del usuario."
                else:
                    user_message=f"{num_imgs} imágenes recibidas del usuario."
                    
                images = image_buffer[user_id]["images"]
                num_imgs = len(images)
                img_data_ids = await save_img_data(
                    request.app.state.mysql_pool, user_id, user_message, images
                )
                del image_buffer[user_id]
                message_data["conversation"] = user_message
                print(f"📦 Procesando imágenes acumuladas de {user_id}: {num_imgs}")
                message_data["conversation"] = user_message
            else:
                print("⏳ Más imágenes podrían llegar, no se procesa aún.")
                return {"status": "ok", "response": "[Imagen recibida, esperando otras...]"}
        else:
            return print("[Mensaje no soportado]")
        
        location_data = location_buffer.get(user_id, {}).get("location", None)
        
        ##---------------Debug------------------##
        print(
            f"📥 Recibido mensaje de: {user_name} ({user_id}) \n"
            f"✉️ Mensaje del usuario: {user_message}\n"
        )          
        

        ##------------------Contexto y estado------------------##        
        state = await build_state(request, user_id, user_name, user_message, img_data_ids, location_data)
        
        redis_session = request.app.state.redis_session
        
        await redis_session.upsert_state(user_id, state)
        await redis_session.append_log(user_id, role="user", content=user_message)


        store.save(user_id, state)

        current_agent = _get_agent_by_name(request.app, state["current_agent"])
        # if current_agent.name == "Railing Agent":
        #     current_agent = request.app.state.agents["General Agent"]
        state["input_items"].append({"role": "user", "content": user_message})
        
        
        #Fuerzo la entrada con General agent, eliminando esto resume con el agente mas reciente, por ahora asi para probar el routing nuevo
        current_agent=_get_agent_by_name(request.app, "General Agent")
        
        ##------------------Ejecucion de SDK------------------##     
        """
        Ejecucion del agente actual con el mensaje del usuario y contexto reconstruido.
        """
        state["context"].current_agent = current_agent.name
        try:
            result = await Runner.run(current_agent, state["input_items"], context=state["context"])
            
        except InputGuardrailTripwireTriggered as e:
            railing_agent = _get_agent_by_name(request.app, "Railing Agent")
            
            guardrail_activated=e.guardrail_result.guardrail.name
            print (f"Guardarail activado {guardrail_activated}")
                        
            if guardrail_activated== "To Mcp Guardrail":
                print("🔀 Redireccionando a Agente MCP ")
                print(f"Razon de redireccion: { e.guardrail_result.output.output_info.reasoning} \n\n")
                current_agent=_get_agent_by_name(request.app, "MCP Agent")
                state["context"].tripwired_trigered_reason= e.guardrail_result.output.output_info.reasoning
                try:
                    result = await Runner.run(current_agent, state["input_items"], context=state["context"])
                except InputGuardrailTripwireTriggered as e:
                    if guardrail_activated== "Basic Relevance Check":
                        print(f"⚠️ Tripwire activado en el input, razon de guardarailes: { e.guardrail_result.output.output_info.reasoning}")
                        railing_agent = _get_agent_by_name(request.app, "Railing Agent")
                        state["context"].tripwired_trigered_reason = e.guardrail_result.output.output_info.reasoning
                        result = await Runner.run(railing_agent,state["input_items"], context=state["context"])
                
            elif guardrail_activated== "To Package Analyst Guardrail":
                print("🔀 Redireccionando a Agente Package Analyst ")
                print(f"Razon de redireccion: { e.guardrail_result.output.output_info.reasoning} \n\n")
                current_agent=_get_agent_by_name(request.app, "Package Analysis Agent")
                state["context"].tripwired_trigered_reason= e.guardrail_result.output.output_info.reasoning
                try:
                    result = await Runner.run(current_agent, state["input_items"], context=state["context"])
                except InputGuardrailTripwireTriggered as e:
                    if guardrail_activated== "Basic Relevance Check":
                        print(f"⚠️ Tripwire activado en el input, razon de guardarailes: { e.guardrail_result.output.output_info.reasoning}")
                        railing_agent = _get_agent_by_name(request.app, "Railing Agent")
                        state["context"].tripwired_trigered_reason = e.guardrail_result.output.output_info.reasoning
                        result = await Runner.run(railing_agent,state["input_items"], context=state["context"])
                
            elif guardrail_activated== "Basic Relevance Check":
                print(f"⚠️ Tripwire activado en el input, razon de guardarailes: { e.guardrail_result.output.output_info.reasoning}")
                state["context"].tripwired_trigered_reason= e.guardrail_result.output.output_info.reasoning
                try:
                    print("🔀 Redireccionando a Railing Agent")
                    result = await Runner.run(railing_agent, state["input_items"], context=state["context"])
                except OutputGuardrailTripwireTriggered as e:
                    railing_agent = _get_agent_by_name(request.app, "Railing Agent")
                    print(f"⚠️ Tripwire activado en el output, razon de guardarailes: { e.guardrail_result.output.output_info.reasoning}")
                    state["context"].tripwired_trigered_reason = e.guardrail_result.output.output_info.reasoning
                    result = await Runner.run(railing_agent,state["input_items"], context=state["context"])
                
        except OutputGuardrailTripwireTriggered as e:
            railing_agent = _get_agent_by_name(request.app, "Railing Agent")
            print(f"⚠️ Tripwire activado en el output, razon de guardarailes: { e.guardrail_result.output.output_info.reasoning}")
            state["context"].tripwired_trigered_reason = e.guardrail_result.output.output_info.reasoning
            result = await Runner.run(railing_agent,state["input_items"], context=state["context"])
            
        current_agent=result._last_agent

        for item in result.new_items:
            try:
                if isinstance(item, MessageOutputItem):
                    content = getattr(item.raw_item, "content", None)
                    text = content[0].text if isinstance(content, list) and content else str(content)
                    response_dict = json.loads(text)
                    response_text = response_dict.get("response")
                    print(f"📤 Respuesta del {current_agent.name}: {response_text}")

                elif isinstance(item, HandoffOutputItem):
                    current_agent = item.target_agent

            except Exception as e:
                print("⚠️ Error al procesar item:", e)

        ##------------------Actualizar estado despues de ejecucion------------------##
        state["input_items"] = result.to_input_list()
        state["current_agent"] = current_agent.name
        
        await redis_session.upsert_state(user_id, state)
        await redis_session.append_log(user_id, role="assistant", content=response_text)
        
        # store.save(user_id, state)
        
        ##------------------Enviar respuesta a WhatsApp------------------##
        await send_text_to_whatsapp(user_id, user_message, response_text, message_id)
 
        ##------------------Calcular Tokens------------------##
        prompt_text = current_agent.instructions(
        RunContextWrapper(state["context"]), current_agent
        ) if callable(current_agent.instructions) else str(current_agent.instructions)
        
        all_text = ""
        for item in state["input_items"]:
            if isinstance(item, dict) and "content" in item:
                all_text += str(item["content"]) + "\n"
        all_text += response_text
        all_text_with_prompt = prompt_text + "\n" + all_text
        tokens_used = count_tokens(all_text_with_prompt)
        print(f"🪙 Tokens usados en la interacción (incluyendo prompt): {tokens_used}") 
        
        
        print("📤 Enviado a WhatsApp ✔️")
        return {"status": "ok", "response": response_text}

    except Exception as e:
        print("❌ Error procesando mensaje de WhatsApp:", e)
        traceback.print_exc()
        return {"error": str(e)}

@app.post("/ManagerUI")
async def manager_ui(request: Request):
    try:
        payload = await request.json()
        print(f'payload obtenido {payload}' )
        if payload.get('request') == 'UsersLastMessages':
            agent_history = await get_users_last_messages(request.app.state.mysql_pool)
            return {"history": agent_history}
        elif payload.get('request') == 'UserHistory':
            request_body = payload.get('request_body')
            user_id=request_body.get('user')
            range=request_body.get('range')
            last_message_id=request_body.get('last_id')
            agent_history = await get_last_messages_by_user(request.app.state.mysql_pool, user_id, limit=range,last_id=last_message_id)
            return {"history": agent_history}
        else:
            return {"error": "Invalid request type."}
    except Exception as e:
        print("❌ Error en ManagerUI:", e)
        return {"error": str(e)}
