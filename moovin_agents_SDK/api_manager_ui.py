from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import create_mysql_pool
from handlers.main_handler import get_users_last_messages, get_last_messages_by_user
import traceback
import os, httpx

prompts_paths={
    "General Agent":"prompts/general_agent.txt",
    "General Prompt":"prompts/general_prompt.txt",
    "MCP Agent":"prompts/mcp_agent.txt",
    "Package Analyst Agent":"prompts/package_analyst.txt",
    "Railing Agent":"prompts/railing_agent.txt",
    "Input":"prompts/input_guardrail_prompt.txt",
    "Output":"prompts/output_guardrail_prompt.txt",
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        mysql_pool = await create_mysql_pool()
        app.state.mysql_pool = mysql_pool  # <-- Agrega esto
        yield
        mysql_pool.close()
        await mysql_pool.wait_closed()
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

@app.post("/Manager")
async def manager_ui(request: Request):
    try:
        payload = await request.json()
        print(f'payload obtenido {payload}' )
        if payload.get('request') == 'UsersLastMessages':
            agent_history = await get_users_last_messages(request.app.state.mysql_pool)
            return {"history": agent_history}
        elif payload.get('request') == 'UserHistory':
            request_body = payload.get('request_body')
            user_id = request_body.get('user')
            range = request_body.get('range')
            last_message_id = request_body.get('last_id')
            agent_history = await get_last_messages_by_user(
                request.app.state.mysql_pool, user_id, limit=range, last_id=last_message_id
            )
            return {"history": agent_history}
        elif payload.get("request")=="Prompt":
            request_body = payload.get('request_body')
            prompt_type = request_body.get('type')
            try:
                with open(prompts_paths[prompt_type], 'r', encoding='utf-8') as file:
                    prompt_content = file.read()
                return {"prompt": prompt_content}
            except KeyError:
                return {"error": "Invalid prompt type."}
        elif payload.get("request")=="Prompt_update":
            request_body = payload.get('request_body')
            new_prompt = request_body.get('updated_prompt')
            prompt_owner = request_body.get('prompt_owner')
            print(f"Nuevo prompt recibido: {new_prompt}")
            try:
                prompt_type = request_body.get('type')
                with open(prompts_paths[prompt_owner], 'w', encoding='utf-8') as file:
                    file.write(new_prompt)
                    
                notify_payload = {
                    "request": "promptUpdate",
                    "body": {
                        "prompt": prompt_owner,    
                        "content": new_prompt
                    }
                }
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.post(f"{os.environ.get('SAC_SDK_URL')}/promptUpdate", json=notify_payload)
                    r.raise_for_status()
                    
                    return {"message": "Prompt updated successfully."}
            except KeyError:
                return {"error": "Invalid prompt type."}
        else:
            return {"error": "Invalid request type."}
    except Exception as e:
        print("❌ Error en ManagerUI:", e)
        traceback.print_exc()
        return {"error": str(e)}
    
    