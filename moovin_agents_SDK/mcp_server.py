from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict
import json
import asyncio

app = FastAPI()

# === TOOL INPUT SCHEMA ===
class CreateTicketInput(BaseModel):
    reason: str
    phone: str
    email: str

class ToolCall(BaseModel):
    id: str
    name: str
    input: Dict

# === ENDPOINT /list-tools ===
def sse_format_tools():
    jsonrpc_msg = {
        "jsonrpc": "2.0",
        "method": "tool_announcement",
        "params": {
            "tools": [
                {
                    "name": "create_ticket",
                    "description": "Crea un ticket de soporte con una razón, número de teléfono y correo.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"},
                            "phone": {"type": "string"},
                            "email": {"type": "string"}
                        },
                        "required": ["reason", "phone", "email"]
                    }
                }
            ]
        }
    }
    print('respuesta del list tools',jsonrpc_msg )
    yield f"data: {json.dumps(jsonrpc_msg)}\n\n"

@app.get("/mcp/list-tools")
async def list_tools():
    return StreamingResponse(sse_format_tools(), media_type="text/event-stream")
    
    
    
# === ENDPOINT /mcp ===
@app.get("/mcp")
async def mcp_sse():
    async def event_stream():
        msg = {
            "jsonrpc": "2.0",
            "method": "tool_announcement",
            "params": {
                "tools": [
                    {
                        "name": "create_ticket",
                        "description": "Crea un ticket de soporte con una razón, número de teléfono y correo.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string"},
                                "phone": {"type": "string"},
                                "email": {"type": "string"}
                            },
                            "required": ["reason", "phone", "email"]
                        }
                    }
                ]
            }
        }
        print('respuesta del list tools',msg )
        yield f"data: {json.dumps(msg)}\n\n"
        while True:
            await asyncio.sleep(60) 
    print('proceso sigue activo')
    return StreamingResponse(event_stream(), media_type="text/event-stream")



# === ENDPOINT /call-tool ===
@app.post("/mcp/call-tool")
async def call_tool(request: Request):
    data = await request.json()
    tool_call = ToolCall(**data)

    if tool_call.name != "create_ticket":
        return {
            "jsonrpc": "2.0",
            "id": tool_call.id,
            "error": {
                "code": -32601,
                "message": f"Herramienta '{tool_call.name}' no encontrada"
            }
        }

    inputs = CreateTicketInput(**tool_call.input)
    output = f"Se creó un ticket con razón: '{inputs.reason}', número: {inputs.phone}, y correo: {inputs.email}'."

    return {
        "jsonrpc": "2.0",
        "id": tool_call.id,
        "result": {
            "output": output
        }
    }
