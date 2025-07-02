from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal
from uuid import uuid4
import os
import requests
from database_handler import get_last_state,save_message,get_user_env
from config import create_mysql_pool, create_tools_pool
from tools import make_get_package_timeline_tool, make_get_SLA_tool
from main import build_agents, MoovinAgentContext
from agents import (
    Runner, MessageOutputItem, HandoffOutputItem, ToolCallItem,
    ToolCallOutputItem, InputGuardrailTripwireTriggered
)
import json
from dotenv import load_dotenv
load_dotenv()

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
    mysql_pool = await create_mysql_pool()
    tools_pool = await create_tools_pool()

    general_agent, package_analysis_agent, ticketing_agent, create_initial_context = build_agents(tools_pool)

    agents = {
        general_agent.name: general_agent,
        package_analysis_agent.name: package_analysis_agent,
        ticketing_agent.name: ticketing_agent,
    }

    app.state.mysql_pool = mysql_pool
    app.state.tools_pool = tools_pool
    app.state.agents = agents
    app.state.create_initial_context = create_initial_context

    yield

    mysql_pool.close()
    await mysql_pool.wait_closed()
    tools_pool.close()
    await tools_pool.wait_closed()

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

@app.post("/ask")
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    try:
        message_data = payload["data"]["message"]
        if "conversation" in message_data:
            user_message = message_data["conversation"]
        elif "locationMessage" in message_data:
            lat = message_data["locationMessage"]["degreesLatitude"]
            lng = message_data["locationMessage"]["degreesLongitude"]
            user_message = f"[Ubicación recibida] Lat: {lat}, Lng: {lng}"
        else:
            user_message = "[Mensaje no soportado]"

        user_id = payload["data"]["key"]["remoteJid"]
        message_id = payload["data"]["key"]["id"]

        is_new = store.get(user_id) is None
        if is_new:
            last_state_record = await get_last_state(request.app.state.mysql_pool, user_id)
            if last_state_record and last_state_record.get("contexto"):
                try:
                    raw_context = last_state_record["contexto"]
                    restored_state = json.loads(raw_context)
                    if isinstance(restored_state, str):
                        restored_state = json.loads(restored_state)
                    restored_context_dict = restored_state["context"]
                    restored_context = MoovinAgentContext(**restored_context_dict)
                    user_env_data = await get_user_env(request.app.state.tools_pool, user_id)
                    restored_context.user_env = user_env_data
                    state = {
                        "context": restored_context,
                        "input_items": restored_state.get("input_items", []),
                        "current_agent": restored_state.get("current_agent", request.app.state.agents["General Agent"].name),
                    }
                except Exception as e:
                    print("⚠️ Error restaurando contexto desde BD, se crea uno nuevo:", e)
                    ctx = request.app.state.create_initial_context()
                    ctx.user_id = user_id
                    user_env_data = await get_user_env(request.app.state.tools_pool, user_id)
                    ctx.user_env = user_env_data

                    state = {
                        "context": ctx,
                        "input_items": [],
                        "current_agent": request.app.state.agents["General Agent"].name,
                    }
            else:
                ctx = request.app.state.create_initial_context()
                ctx.user_id = user_id
                user_env_data = await get_user_env(request.app.state.tools_pool, user_id)
                ctx.user_env = user_env_data

                state = {
                    "context": ctx,
                    "input_items": [],
                    "current_agent": request.app.state.agents["General Agent"].name,
                }
            store.save(user_id, state)
        else:
            state = store.get(user_id)
           
        current_agent = _get_agent_by_name(request.app, state["current_agent"])
        state["input_items"].append({"role": "user", "content": user_message})
        result = await Runner.run(current_agent, state["input_items"], context=state["context"])
        print("🔄 Resultado de la ejecución del agente:", result)
        response_text = "🤖 No hay respuesta disponible."
        for item in result.new_items:
            try:
                if isinstance(item, MessageOutputItem):
                    if hasattr(item, "raw_item") and hasattr(item.raw_item, "content"):
                        content = item.raw_item.content
                        if isinstance(content, list) and len(content) > 0 and hasattr(content[0], "text"):
                            response_text = content[0].text
                        else:
                            response_text = str(content)
                    else:
                        response_text = str(item)
                elif isinstance(item, HandoffOutputItem):
                    current_agent = item.target_agent
            except Exception as e:
                print("⚠️ Error al procesar item:", e)

        state["input_items"] = result.to_input_list()
        state["current_agent"] = current_agent.name
        store.save(user_id, state)
        state_to_save = state.copy() 

        if hasattr(state_to_save["context"], "model_dump"):
            state_to_save["context"] = state_to_save["context"].model_dump()

        context_json = json.dumps(state_to_save)
        await save_message(
            request.app.state.mysql_pool,
            user_id,
            user_message,
            response_text,
            context_json
        )

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

        r = requests.post(url, json=payload, headers=headers)
        print("📤 Enviado a WhatsApp:", r.text)

        return {"status": "ok", "response": response_text}

    except Exception as e:
        print("❌ Error procesando mensaje de WhatsApp:", e)
        return {"error": str(e)}



# @app.post("/chat", response_model=ChatResponse)
# async def chat(req: ChatRequest):
#     is_new = not req.conversation_id or store.get(req.conversation_id) is None

#     if is_new:
#         cid = uuid4().hex
#         ctx = create_initial_context()
#         state = {
#             "context": ctx,
#             "input_items": [],
#             "current_agent": general_agent.name,
#         }
#         store.save(cid, state)
#     else:
#         cid = req.conversation_id
#         state = store.get(cid)

#     current_agent = _get_agent_by_name(state["current_agent"])
#     state["input_items"].append({"role": "user", "content": req.message})

#     try:
#         result = await Runner.run(current_agent, state["input_items"], context=state["context"])
#     except InputGuardrailTripwireTriggered as e:
#         return ChatResponse(
#             conversation_id=cid,
#             current_agent=current_agent.name,
#             messages=[MessageResponse(content="Guardrail activated. Input rejected.", agent=current_agent.name)],
#             events=[],
#             context=state["context"].model_dump(),
#             agents=_list_agents(),
#             guardrails=[],
#         )

#     messages, events = [], []
#     for item in result.new_items:
#         if isinstance(item, MessageOutputItem):
#             msg = item.output.content if hasattr(item.output, "content") else str(item.output)
#             messages.append(MessageResponse(content=msg, agent=item.agent.name))
#         elif isinstance(item, HandoffOutputItem):
#             events.append(AgentEvent(
#                 id=uuid4().hex,
#                 type="handoff",
#                 agent=item.source_agent.name,
#                 content=f"{item.source_agent.name} -> {item.target_agent.name}",
#             ))
#             current_agent = item.target_agent
#         elif isinstance(item, ToolCallItem):
#             events.append(AgentEvent(
#                 id=uuid4().hex,
#                 type="tool_call",
#                 agent=item.agent.name,
#                 content=str(item.raw_item.name)
#             ))
#         elif isinstance(item, ToolCallOutputItem):
#             events.append(AgentEvent(
#                 id=uuid4().hex,
#                 type="tool_output",
#                 agent=item.agent.name,
#                 content=str(item.output)
#             ))

#     state["input_items"] = result.to_input_list()
#     state["current_agent"] = current_agent.name
#     store.save(cid, state)

#     return ChatResponse(
#         conversation_id=cid,
#         current_agent=current_agent.name,
#         messages=messages,
#         events=events,
#         context=state["context"].model_dump(),
#         agents=_list_agents(),
#         guardrails=[],
#     )
