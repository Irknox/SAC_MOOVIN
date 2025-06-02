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
import aiomysql
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
load_dotenv()

# ----------------- Configuración de MySQL ------------------
MYSQL_HOST = os.environ.get('Db_HOST')
MYSQL_USER = os.environ.get('Db_USER')
MYSQL_PASSWORD = os.environ.get('Db_PASSWORD')
MYSQL_DB = os.environ.get('Db_NAME')
MYSQL_PORT = int(os.environ.get('Db_PORT', 3306))

mysql_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mysql_pool
    mysql_pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        port=MYSQL_PORT,
        autocommit=True
    )
    async with mysql_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INT NOT NULL AUTO_INCREMENT,
                    session_id VARCHAR(255) NOT NULL,
                    user_message TEXT NOT NULL,
                    agent_response TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id), 
                    KEY session_id (session_id)
                )
            """)
    yield
    mysql_pool.close()
    await mysql_pool.wait_closed()

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
async def get_history(session_id, limit=15):
    async with mysql_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT user_message, agent_response, timestamp
                FROM chat_history
                WHERE session_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (session_id, limit))
            results = await cur.fetchall()
            results = list(results)
            results.reverse()
            return results

async def save_message(session_id, user_message, agent_response):
    async with mysql_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO chat_history (session_id, user_message, agent_response) 
                VALUES (%s, %s, %s)
            """, (session_id, user_message, agent_response))

async def populate_memory_from_history(memory, session_id):
    history = await get_history(session_id)
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

graph_builder = StateGraph(AgentState)

async def chat_node(state: AgentState):
    session_id = state.session_id
    user_input = state.user_input
    recent_activity=await populate_memory_from_history(agent_executor.memory, session_id)
    print(f"Valor de recent activity: {recent_activity}")
    result = await agent_executor.ainvoke({"input": user_input, "recent_activity": recent_activity})
    response = result["output"] if "output" in result else str(result)

    # Guardar en chat_history
    await save_message(session_id, user_input, response)
    return {"user_input": "", "session_id": session_id}

graph_builder.add_node("chat_node", chat_node)
graph_builder.set_entry_point("chat_node")
graph_builder.set_finish_point("chat_node")
compiled_graph = graph_builder.compile()


# ----------------- Clases para las entradas de los Endpoints ------------------

class UserInput(BaseModel):
    message: str
    session_id: str


# ----------------- Endpoints ------------------

@app.post("/ask")
async def ask(user_input: UserInput):
    initial_state = AgentState(user_input=user_input.message, session_id=user_input.session_id)
    await compiled_graph.ainvoke(initial_state)
    history = await get_history(user_input.session_id, limit=1)
    last_response = history[-1]["agent_response"] if history else "Lo siento, algo salió mal."
    return {"model_response": last_response}