from fastapi import FastAPI
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langgraph.graph import StateGraph
from langchain.prompts import PromptTemplate
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv
import os
from app.tools import TOOLS
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import re
import phonenumbers
from app.database_handler import get_history, save_message,get_user_env
from app.config import create_mysql_pool, create_tools_pool



load_dotenv()
# ----------------- Configuración de la aplicación FastAPI ------------------
mysql_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mysql_pool
    mysql_pool = await create_mysql_pool()
    global tools_pool
    tools_pool = await create_tools_pool()
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

# ----------------- Configuración del LLM y Agente ------------------
OPENAI_API_KEY = os.environ.get("OPEN_AI_API")
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model="gpt-4o")
tools = TOOLS

#Obtener prompt
with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r", encoding="utf-8") as f:
    prompt_content = f.read()

if prompt_content.startswith('prompt='):
    prompt_content = prompt_content.split('=', 1)[1].strip().strip('"').strip("'")

#Crear el PromptTemplate
prompt = PromptTemplate.from_template(prompt_content)

# Crear el agente de OpenAI con tools y prompt
memory = ConversationBufferMemory(return_messages=True,input_key="input")
agent = create_openai_functions_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, memory_key="chat_history", verbose=True)


# ----------------- Funciones para chat_history ------------------
async def populate_memory_from_history(memory, session_id):
    history = await get_history(mysql_pool, session_id)
    memory.clear()
    recent_activity = False
    now = datetime.utcnow()
    print(f"[DEBUG] now (UTC): {now}")

    for msg in history:
        timestamp = msg.get('timestamp')
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    print(f"[ERROR] Error convirtiendo timestamp: {e}")
            if now - timestamp <= timedelta(minutes=15):
                recent_activity = True
        memory.chat_memory.add_user_message(f"[{timestamp}] {msg['user_message']}")
        memory.chat_memory.add_ai_message(f"[{timestamp}] {msg['agent_response']}")
    if recent_activity:
        memory.chat_memory.add_user_message("Nota del sistema: La conversación es reciente, no es necesario saludar.")
    else:
        memory.chat_memory.add_user_message("Nota del sistema: La conversación es antigua, por favor saluda al usuario antes de continuar.")
    return recent_activity

# ----------------- Estado del agente ------------------

class AgentState(BaseModel):
    user_input: str
    session_id: str
    user_phone: str
    message_id: str
    message_original: str
    response: str = ""
    user_env: dict = {}
    user_env: str = ""

# ------------------ Nodos ------------------
#Agente
async def agent_node(state: AgentState):
    session_id = state.session_id
    user_input = state.user_input
    
    recent_activity=await populate_memory_from_history(agent_executor.memory, session_id)
    
    result = await agent_executor.ainvoke({
        "input": user_input,
        "recent_activity": recent_activity,
        "user_env": state.user_env
    })
    response = result["output"] if "output" in result else str(result)
    
    await save_message(mysql_pool, session_id, user_input, response)
    return AgentState(
        user_input="",
        session_id=session_id,
        user_phone=state.user_phone,
        message_id=state.message_id,
        message_original=state.message_original,
        response=response,
        user_env=state.user_env
    )

# Enviar mensaje a WhatsApp
async def enviar_mensaje_node(state):
    Whatsapp_URL = os.environ.get("Whatsapp_URL")
    Whatsapp_API_KEY = os.environ.get("Whatsapp_API_KEY")

    url = f"{Whatsapp_URL}/message/sendText/SAC-Moovin"

    payload = {
        "number": state.user_phone.replace("@s.whatsapp.net", ""), 
        "text": state.response,
        "delay": 100,
        "linkPreview": False,
        "mentionsEveryOne": False,
        "mentioned": [state.user_phone],
        "quoted": {
            "key": {"id": state.message_id},
            "message": {"conversation": state.message_original}
        }
    }

    headers = {
        "apikey": Whatsapp_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        import requests
        response = requests.post(url, json=payload, headers=headers)
        print("📤 Mensaje enviado:", response.text)
    except Exception as e:
        print("❌ Error al enviar mensaje:", e)
    return state

# Crear el entorno del usuario
async def user_environment_node(state: AgentState):
    user_phone = state.user_phone
    user_phone = re.sub(r"[^\d+]", "", user_phone) 
    try:
        if not user_phone.startswith("+"):
            user_phone = "+" + user_phone
            parsed = phonenumbers.parse(user_phone, None)
        else:
            parsed = phonenumbers.parse(user_phone, None)
        user_phone = str(parsed.national_number)
    except Exception as e:
        user_phone = re.sub(r"\D", "", user_phone)
    user_environment= await get_user_env(tools_pool, 85813601)
    state.user_env = user_environment
    return state

# Añadir los nodos al grafo
graph_builder = StateGraph(AgentState)
graph_builder.add_node("user_environment_node", user_environment_node)
graph_builder.add_node("agent_node", agent_node)
graph_builder.add_node("enviar_mensaje_node", enviar_mensaje_node)

graph_builder.add_edge("user_environment_node", "agent_node")
graph_builder.add_edge("agent_node", "enviar_mensaje_node")

graph_builder.set_entry_point("user_environment_node")
graph_builder.set_finish_point("enviar_mensaje_node")
compiled_graph = graph_builder.compile()

# ----------------- Clases para las entradas de los Endpoints ------------------
class UserInput(BaseModel):
    message: str
    session_id: str
# ----------------- Endpoints ------------------
@app.post("/ask", summary="Recibe mensajes desde WhatsApp", description="Recibe, procesa y responde usando LangChain y WhatsApp API.")
async def receive_message(payload: dict):
    try:
        message_data = payload["data"]["message"]
        if "conversation" in message_data:
            message = message_data["conversation"]
        elif "locationMessage" in message_data:
            lat = message_data["locationMessage"]["degreesLatitude"]
            lng = message_data["locationMessage"]["degreesLongitude"]
            message = f"[Ubicación recibida] Lat: {lat}, Lng: {lng}"
            # Aquí puedes guardar lat/lng en el estado si lo necesitas
        else:
            message = "[Mensaje no soportado]"

        session_id = payload["data"]["instanceId"]
        user_phone = payload["data"]["key"]["remoteJid"]
        message_id = payload["data"]["key"]["id"]

        initial_state = AgentState(
            user_input=message,
            session_id=session_id,
            user_phone=user_phone,
            message_id=message_id,
            message_original=message
        )

        await compiled_graph.ainvoke(initial_state)
        return {"status": "ok"}

    except Exception as e:
        print(f"[ERROR] Fallo procesando el payload: {e}")
        return {"error": "Payload inválido o incompleto."}

