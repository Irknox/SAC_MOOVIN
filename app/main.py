from fastapi import FastAPI
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import os
from app.tools import TOOLS
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


app = FastAPI()

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # o ["*"] para permitir todos los orígenes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPEN_AI_API")
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model="gpt-4o")

#Tools del modelo
tools = TOOLS

# Estado del agente
class AgentState(BaseModel):
    user_input: str
    chat_history: list  # [{"user":..., "bot":...}]

# Constructor del grafo (flujo)
graph = StateGraph(AgentState)

# Nodo que maneja cada mensaje
async def chat_node(state: AgentState):
    # Prompt con contexto del historial
    context = "\n".join([f"Usuario: {msg['user']}\nBot: {msg['bot']}" for msg in state.chat_history])
    prompt = f"{context}\nUsuario: {state.user_input}\nBot:"
    response = await llm.ainvoke(prompt)

    #Update del historial
    new_history = state.chat_history + [{"user": state.user_input, "bot": response.content}]
    
    return {"user_input": "", "chat_history": new_history}

# Configuración del grafo (Flujo)
graph.add_node("chat_node", chat_node)
graph.set_entry_point("chat_node")
graph.set_finish_point("chat_node")
compiled_graph = graph.compile()

#Clase para recibir input del usuario
class UserInput(BaseModel):
    message: str

#------------------------------Endpoints-----------------------------#

## Endpoint para recibir mensajes del usuario
@app.post("/ask")
async def ask(user_input: UserInput):
    initial_state = AgentState(user_input=user_input.message, chat_history=[])
    result = await compiled_graph.ainvoke(initial_state)
    return {"model_response": result["chat_history"][-1]["bot"]}