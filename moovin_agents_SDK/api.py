from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal,Tuple
import re, os, glob
import tempfile
import requests
from handlers.main_handler import save_message, get_user_env, save_img_data, reverse_geocode_osm
from config import create_mysql_pool, create_tools_pool
from main import build_agents, MoovinAgentContext
from agents import (Runner, MessageOutputItem, HandoffOutputItem, InputGuardrailTripwireTriggered,RunContextWrapper,OutputGuardrailTripwireTriggered)
import json, ast
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
from agents.model_settings import ModelSettings


from zoneinfo import ZoneInfo
now_cr = datetime.now(ZoneInfo("America/Costa_Rica")).isoformat()

def now_cr_iso() -> str:
    return datetime.now(ZoneInfo("America/Costa_Rica")).isoformat()

image_buffer: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
location_buffer: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

text_buffer: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
text_timers: Dict[str, "asyncio.TimerHandle"] = {}

TEXT_BUFFER_WINDOW_SECONDS = 4
TEXT_BUFFER_MAX_USERS = 50
TEXT_BUFFER_MAX_MSGS = 20

load_dotenv()
client = OpenAI()

##----------------------------Funciones Auxiliares----------------------------##

##----------------------------Prompts----------------------------##
SEMVER_RE = re.compile(r"_v(\d+\.\d+\.\d+\.\d+)\.txt$")
prompt_bases = {
    "General Prompt":           "general_prompt",
    "Package Analyst Agent":    "package_analyst",
    "General Agent":            "general_agent",
    "MCP Agent":                "mcp_agent",
    "Railing Agent":            "railing_agent",
    "Input":                    "input_guardrail_prompt",
    "Output":                   "output_guardrail_prompt",
}
def _parse_semver_tuple(v: str) -> Tuple[int,int,int,int]:
    return tuple(int(x) for x in v.split("."))  # "1.0.0.7" -> (1,0,0,7)

def _extract_version_from_name(filename: str) -> Optional[Tuple[int,int,int,int]]:
    m = SEMVER_RE.search(filename)
    if m:
        return _parse_semver_tuple(m.group(1))
    return None

def _find_latest_versioned_file(base_dir: str, slug: str) -> Optional[str]:
    """
    Busca el .txt con mayor versión para un slug dado dentro de base_dir.
    Formato esperado: slug_vX.Y.Z.W.txt
    """
    pattern = os.path.join(base_dir, f"{slug}_v*.txt")
    candidates = glob.glob(pattern)
    if not candidates:
        return None

    best_path = None
    best_ver = None
    for path in candidates:
        ver = _extract_version_from_name(os.path.basename(path))
        if ver is None:
            continue
        if best_ver is None or ver > best_ver:
            best_ver = ver
            best_path = path
    return best_path

def _load_initial_prompts() -> dict:
    """
    Lee .txt versionados (ultimo disponible) o, si no hay, los .txt planos.
    """
    base_dir = os.path.join(os.path.dirname(__file__), "prompts")

    def read_best(slug: str, fallback_plain: str) -> str:
        latest = _find_latest_versioned_file(base_dir, slug)
        target = latest or os.path.join(base_dir, fallback_plain)
        with open(target, "r", encoding="utf-8") as f:
            return f.read()

    return {
        "General Prompt":        read_best(prompt_bases["General Prompt"],        "general_prompt.txt"),
        "Package Analyst Agent": read_best(prompt_bases["Package Analyst Agent"], "package_analyst.txt"),
        "General Agent":         read_best(prompt_bases["General Agent"],         "general_agent.txt"),
        "MCP Agent":             read_best(prompt_bases["MCP Agent"],             "mcp_agent.txt"),
        "Railing Agent":         read_best(prompt_bases["Railing Agent"],         "railing_agent.txt"),
        "Input":                 read_best(prompt_bases["Input"],                 "input_guardrail_prompt.txt"),
        "Output":                read_best(prompt_bases["Output"],                "output_guardrail_prompt.txt"),
    }
    
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
            if img_data_ids:
                restored_context.imgs_ids = img_data_ids
            if location_data:
                restored_context.location_sent=location_data or {}
            for field in [
                "input_tripwired_trigered_reason",
                "output_tripwired_trigered_reason",
                "handoff_from",
                "handoff_to",
                "handoff_reason"]:
                setattr(restored_context, field, "")
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
    url = f"{os.environ.get('Whatsapp_URL')}/message/sendText/Silver AI"
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

async def persist_session_to_mysql(app, cid: str, session_obj: dict):
    mysql_pool = app.state.mysql_pool
    redis_session=app.state.redis_session


    state = session_obj.get("state", {}) or {}
    ctx = state.get("context")
    if hasattr(ctx, "model_dump"):
        state["context"] = ctx.model_dump()
        
    
    state["input_items"]=await redis_session.get_audit_items(cid)
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
    while True:
        try:
            cids = await redis_session.due_sessions()
            for cid in cids:
                session_obj = await redis_session.get_session(cid)
                if not session_obj:
                    continue
                try:
                    await persist_session_to_mysql(app, cid, session_obj)
                    "Se intenta guardara la memoria"
                finally:
                    await redis_session.clear_audit_items(cid)
                    await redis_session.delete_session(cid)

                    print(f"Se limpio la memoria del usuario {cid}")
        except Exception as e:
            print(f"[flush_worker] error: {e}")
        await asyncio.sleep(30)  # frecuencia de barrido

##----------------------------Prompts----------------------------##

def _parse_output_dict(s: str) -> dict | None:
    """Intenta parsear el 'output' que viene como string.
       Primero JSON, si falla probamos literal_eval (formato Python).
    """
    if not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except Exception:
        try:
            parsed = ast.literal_eval(s)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
        
##--------------------Classes--------------------##
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
        
        app.state.prompts = _load_initial_prompts()
        
        
        general_agent, package_analysis_agent, mcp_agent, railing_agent ,create_initial_context = await build_agents(tools_pool,mysql_pool,app.state.prompts)
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

def _get_agent_by_name(app, name: str):
    agents = getattr(app.state, "agents", {}) or {}
    if not agents:
        return None
    if name in agents:
        return agents[name]
    lname = (name or "").strip().lower()
    for k, v in agents.items():
        if k.lower() == lname:
            return v
    return agents.get("Railing Agent") or agents.get("General Agent") or next(iter(agents.values()), None)


def _extract_guardrail_info(exc) -> Tuple[str, str, Optional[str], Optional[bool]]:
    """
    Devuelve (guardrail_name, reasoning, correct_agent, passed) a partir de la excepción del guardrail.
    - reasoning: explicación del porqué
    - correct_agent: nombre sugerido por el guardrail (si aplica)
    - passed: bool si el guardrail 'pasó' su chequeo; None si no viene
    """
    gr = getattr(getattr(exc, "guardrail_result", None), "guardrail", None)
    guardrail_name = getattr(gr, "name", "") or ""

    out = getattr(getattr(exc, "guardrail_result", None), "output", None)
    info = getattr(out, "output_info", None)

    reasoning: str = ""
    correct_agent: Optional[str] = None
    passed: Optional[bool] = None

    if info is not None:
        reasoning = getattr(info, "reasoning", "") or ""
        correct_agent = getattr(info, "correct_agent", None)
        passed = getattr(info, "passed", None)
        
        if isinstance(info, dict):
            reasoning = info.get("reasoning", reasoning) or ""
            correct_agent = info.get("correct_agent", correct_agent)
            passed = info.get("passed", passed)
    print (f"Guardarail activado: {guardrail_name}, reasoning: {reasoning}, Agente correcto:{correct_agent}")
    return guardrail_name, reasoning, correct_agent, passed

async def run_sdk(app, user_id, state, start_agent, max_hops: int = 3):
    """
    Ejecuta el SDK con ruteo guiado por guardrails y un fallback a el Railing Agent
    """
    active_agent = start_agent
    items = state.get("input_items", [])
    ctx = state["context"]
    redis_session=app.state.redis_session

    for _ in range(max_hops):
        try:
            return await Runner.run(active_agent, items, context=ctx)
        except InputGuardrailTripwireTriggered as exc_in:
            guardrail_name, reasoning, correct_agent, passed = _extract_guardrail_info(exc_in)
            ctx.input_tripwired_trigered_reason = reasoning
        
            audit_item={
                "action":"tripwire_triggered",
                "guardrail":guardrail_name,
                "reason":reasoning
            }
            
            await redis_session.append_audit_items(user_id,audit_item)
            
            if correct_agent:
                print(f"🔀 Redireccionando a {correct_agent}")
            next_name = (correct_agent or "Railing Agent").strip()
            next_agent = _get_agent_by_name(app, next_name)
            if next_agent is None or next_agent is active_agent:
                next_agent = _get_agent_by_name(app, "Railing Agent")
            active_agent = next_agent
            continue
        except OutputGuardrailTripwireTriggered as exc_out:
            guardrail_name, reasoning, correct_agent, passed = _extract_guardrail_info(exc_out)
            ctx.output_tripwired_trigered_reason = reasoning
            
            audit_item={
                "action":"tripwire_triggered",
                "guardrail":guardrail_name,
                "reason":reasoning
            }
            await redis_session.append_audit_items(user_id,audit_item)
            
            
            active_agent = _get_agent_by_name(app, "Railing Agent")
            continue
    return await Runner.run(_get_agent_by_name(app, "Railing Agent"), items, context=ctx)


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
        print(f"User id es: {user_id}")
        message_id = data_item["key"]["id"]
        
        img_data_ids= []
        
        ## ------------------------Procesamiento de mensajes de texto------------------------ ##
        if "conversation" in message_data:
            raw_text = (message_data.get("conversation") or "").strip()
            if not raw_text:
                return {"status": "ok", "response": "[Mensaje vacío ignorado]"}
            now = datetime.utcnow()
            if user_id in text_buffer:
                buf = text_buffer[user_id]
                buf["messages"].append(raw_text)
                buf["last_seen"] = now
                if len(buf["messages"]) > TEXT_BUFFER_MAX_MSGS:
                    buf["messages"] = buf["messages"][-TEXT_BUFFER_MAX_MSGS:]
            else:
                if len(text_buffer) >= TEXT_BUFFER_MAX_USERS:
                    text_buffer.popitem(last=False)
                text_buffer[user_id] = {
                    "messages": [raw_text],
                    "last_seen": now
                }

            await asyncio.sleep(TEXT_BUFFER_WINDOW_SECONDS)

            last_seen = text_buffer[user_id]["last_seen"]
            if (datetime.utcnow() - last_seen).total_seconds() >= TEXT_BUFFER_WINDOW_SECONDS:
                msgs = text_buffer[user_id]["messages"][:]
                del text_buffer[user_id]
                consolidated = "\n".join(msgs).strip()
                user_message = consolidated
                message_data["conversation"] = user_message  
            else:
                return {"status": "ok", "response": "[Mensaje recibido, esperando otros...]"}


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
        
        user_message_for_audit ={
            "role":"user",
            "content":user_message,
            "date": now_cr_iso(),
        }
        await redis_session.append_audit_items(user_id, user_message_for_audit)

        current_agent = _get_agent_by_name(request.app, state["current_agent"])
        # if current_agent.name == "Railing Agent":
        #     current_agent = request.app.state.agents["General Agent"]
        state["input_items"].append({"role": "user", "content": user_message})
        
        
        #Fuerzo la entrada con General agent, eliminando esto se resumira con el ultimo agente que se interactuo
        current_agent=_get_agent_by_name(request.app, "General Agent")
        previous_count  = len(state.get("input_items", []))
        ##------------------Ejecucion de SDK------------------##     
        """
        Ejecucion del agente actual con el mensaje del usuario y contexto reconstruido.
        """   
        result = await run_sdk(request.app, user_id, state, current_agent)
        current_agent=result._last_agent
        response_text = None
        final_out = getattr(result, "final_output", None)
        for item in result.new_items:
            try:
                if isinstance(final_out, str):
                    response_text = final_out.strip()
                elif isinstance(item, MessageOutputItem):
                    content = getattr(item.raw_item, "content", None)
                    print(f"Esto es content: {content}")
                    text = content[0].text if isinstance(content, list) and content else str(content)
                    response_dict = json.loads(text)
                    response_text = response_dict.get("response")
                    print(f"📤 Respuesta del {current_agent.name}: {response_text}")  
                elif isinstance(item, HandoffOutputItem):
                    current_agent = item.target_agent
            except Exception as e:
                print("⚠️ Error al procesar item:", e)

        ##------------------Actualizar estado despues de ejecucion------------------##
        # --- estado oficial para el agente ---
        full_list = result.to_input_list()
        state["input_items"] = full_list
        state["current_agent"] = current_agent.name
        await redis_session.upsert_state(user_id, state)
        await redis_session.append_log(user_id, role="assistant", content=response_text)


        if previous_count > len(full_list):
            previous_count = 0

        new_slice = full_list[previous_count:]

        def is_user_echo(item):
            return isinstance(item, dict) and item.get("role") == "user" and not item.get("date")

        delta_items = [it for it in new_slice if not is_user_echo(it)]
        
        
        if delta_items:
            ctx = state.get("context", None)

            ticket_url_map = {}
            if getattr(ctx, "issued_tickets_info", None):
                for t in ctx.issued_tickets_info:
                    tn = (t or {}).get("TicketNumber")
                    url = (t or {}).get("DevURL")
                    if tn and url:
                        ticket_url_map[str(tn)] = url

            enriched_any = False
            for it in delta_items:
                if it.get("type") == "function_call_output" and "output" in it:
                    parsed = _parse_output_dict(it["output"])
                    if not isinstance(parsed, dict):
                        continue

                    tn = parsed.get("TicketNumber")
                    if tn is None:
                        tn = parsed.get("ticket") or parsed.get("ticket_number")

                    if tn is not None:
                        tn_str = str(tn)
                        if tn_str in ticket_url_map:
                            dev_url = ticket_url_map[tn_str]
                            parsed["DevURL"] = dev_url
                            it["ticket_url"] = dev_url
                            it["output"] = json.dumps(parsed, ensure_ascii=False)
                            enriched_any = True

            if ctx and getattr(ctx, "issued_tickets_info", None):
                print(f"Informacion del ticket: {ctx.issued_tickets_info}")

            await redis_session.append_audit_items(user_id, delta_items)
            
        agent_message_human = {
            "role": "assistant",
            "content": response_text,
            "agent": current_agent.name,
            "date":  now_cr_iso(),
        }
        
        await redis_session.append_audit_items(user_id, agent_message_human)
        
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
        print("❌ Error en el flujo general:",e)
        traceback.print_exc()
        return {"error": str(e)}


@app.post("/promptUpdate")
async def update_prompt_executed(request: Request):
    payload = await request.json()
    if (payload.get("request")=="promptUpdate"):
        body=payload.get("body")
        prompt_to_update=body.get("prompt")
        new_prompt=body.get("content")
        try:
            request.app.state.prompts[prompt_to_update]=new_prompt
            print(f"Prompt actualizado")
        except Exception as e:
            print(f"error al cambiar el prompt{e}")
        
    return False