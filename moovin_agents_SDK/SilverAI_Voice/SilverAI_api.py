from fastapi import FastAPI, Body, HTTPException, Header
from typing import Dict, Any
from handlers.db_handlers import create_mysql_pool, create_tools_pool
from tools.api_tools import Make_get_package_timeline_tool,Make_request_to_pickup_tool,Make_request_electronic_receipt_tool, Make_package_damaged_tool,Make_escalate_call_tool
import os
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_mysql_pool()
    app.state.tools_pool = await create_tools_pool()
    app.state.tools = {
        "check_package_status": Make_get_package_timeline_tool(app.state.tools_pool),
        "pickup_in_store": Make_request_to_pickup_tool(app.state.tools_pool),
        "electronic_receipt": Make_request_electronic_receipt_tool(app.state.tools_pool),
        "report_package_damaged": Make_package_damaged_tool(app.state.tools_pool),
        "escalate_call": Make_escalate_call_tool()
    }
    yield
    app.state.db_pool.close()
    await app.state.db_pool.wait_closed()
app = FastAPI(lifespan=lifespan)

Token_API=os.environ.get('SILVERAI_API_TOKEN')
@app.post("/SilverAPI")
async def silver_brain_endpoint(
    payload: Dict[str, Any] = Body(...),
    auth_token: Optional[str] = Header(None, alias="auth_token")

):
    """

    Endpoint para procesar solicitudes al SilverBrain.

    """
    if auth_token != Token_API:
        print(f"Intento de acceso no autorizado con token: {auth_token}")
        raise HTTPException(status_code=401, detail="No autorizado: Token inválido")
    try:
        tool_requested = payload.get("request")
        params = payload.get("params", {})
        if tool_requested in app.state.tools:
            selected_tool = app.state.tools[tool_requested]
            if tool_requested == "check_package_status":
                result = await selected_tool(
                    package_id=params.get("package"), 
                    phone=params.get("phone")
                )
            elif tool_requested == "pickup_in_store":
                result = await selected_tool(
                    package=params.get("package"),
                    description=params.get("description")
                )
            elif tool_requested == "electronic_receipt":
                result = await selected_tool(
                    package=params.get("package"),
                    reason=params.get("reason"),
                    legal_name=params.get("legal_name"),
                    legal_id=params.get("legal_id"),
                    full_address=params.get("full_address"),
                )
            elif tool_requested == "report_package_damaged":
                result = await selected_tool(
                    package=params.get("package"),
                    description=params.get("description")
                )
            elif tool_requested == "escalate_call":
                result = await selected_tool(
                    user_phone=params.get("user_phone"),
                    channel=params.get("channel")
                )
            return {"status": "success", "data": result}

        return {"status": "error", "message": "Herramienta no encontrada"}
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))