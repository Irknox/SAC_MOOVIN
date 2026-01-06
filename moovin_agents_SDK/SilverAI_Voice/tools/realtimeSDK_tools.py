from agents import function_tool, RunContextWrapper
import os, asyncio, json
import requests
from SilverAI_Brain.brain import BrainRunner, BrainContext, AgentInputItem, ToolOutputResult
from pydantic import BaseModel, Field
from handlers.db_handlers import get_last_interactions_summary,get_id_package,get_package_historic
from handlers.aux_handlers import create_pickup_ticket,request_electronic_receipt,_parse_date_cr,report_package_damaged
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

class ThinkInput(BaseModel):
    query: str = Field(description="La pregunta o solicitud completa del usuario que SilverAI no puede responder sin la lógica especializada.")

ARI_CONTROL_URL = os.getenv("ARI_CONTROL_URL")
AMI_CONTROL_TOKEN = os.getenv("AMI_CONTROL_TOKEN")


DELIVERED_STATES= {"DELIVERED", "DELIVEREDCOMPLETE"}
RETURN_STATES= {"RETURN"}
FAILED_STATES= {"FAILED","DELETEPACKAGE","CANCELNOCHARGE","CANCEL"}

CR_TZ = ZoneInfo("America/Costa_Rica")

@function_tool(
    name_override="escalate_call",
    description_override="Escala inmediatamente a un asistente Humano. Úsala ÚNICAMENTE cuando el usuario solicite hablar con un Humano."
)
async def escalate_call(ctx: RunContextWrapper, target_ext: int = 90000, mode: str = "redirect"):
    context_obj = getattr(ctx, "context", None)
    call_id = None
    if isinstance(context_obj, dict):
        print(f"Call Id es un Dict")
        call_id = context_obj.get("call_id")
    else:
        print(f"Call Id NO es un Dict")
        call_id = getattr(context_obj, "call_id", None)

    if not call_id:
        print("Missin Call ID in context")
        return {"status": "error", "reason": "missing_call_id_in_context"}
    
    if not AMI_CONTROL_TOKEN:
        print("falta Control ARI en ENV")
        return {"status": "error", "reason": "missing AMI_CONTROL_TOKEN"}
    
    print(f"Usando Escalate Tool 🧗 con call_id {call_id} a la extension {target_ext} con mode {mode}")
    url = ARI_CONTROL_URL.rstrip("/") + "/transfer"
    payload = {"call_id": call_id, "target_ext": int(target_ext), "mode": mode}
    headers = {
        "x-ari-control-token": AMI_CONTROL_TOKEN,
        "Content-Type": "application/json",
    }

    def _do_request():
        return requests.post(url, headers=headers, json=payload, timeout=8)
    try:
        resp = await asyncio.to_thread(_do_request)
        data = None
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        print(f"Este es el valor de data: {data}")
        if resp.ok:
            print(f"Solicitud enviada a ari, respuesta: {data}")
            return data
        else:
            print(f"Error en respuesta, respuesta {data}")
            return {"status": "error", "http_status": resp.status_code, "response": data}
    except Exception as e:
        print(f"Error al usar el tool, Detalles: {e}")
        return {"status": "error", "reason": "request_failed", "detail": repr(e)}

def Make_think_tool(call_id: str, brain_runner: BrainRunner):
    """
    Función fábrica que crea y devuelve una instancia de la herramienta 'think' 
    con las variables call_id y brain_runner encapsuladas (closure).
    """
    
    @function_tool(
        name_override="think",
        description_override="Has una consulta especializada a un sistema de agentes multi-nodo para responder preguntas complejas sobre rastreo, tarifas, ubicaciones, etc."
    )
    async def think(query: str) -> str:
        print(f"Pensando 🧠...{query}")
        try:
            if not brain_runner:
                return "Error: Brain no inicializado."
            input_item = {"role": "user", "content": query}
            brain_context = BrainContext(session_id=call_id, call_id=call_id)
            result: ToolOutputResult = await brain_runner.execute_query([input_item], brain_context)
            if result.final_output:
                if isinstance(result.final_output, dict):
                    return result.final_output.get("text", str(result.final_output))
                return str(result.final_output)
            return "El sistema no pudo generar una respuesta."
        except Exception as e:
            print(f"[ERROR] think tool: {e}")
            return "Error en la consulta especializada."
    return think

@function_tool(
        name_override="remember_last_interactions",
        description_override="Herramienta que permite obtener un resumen de las ultimas 3 interacciones del usuario en caso de existir."
    )
async def remember_last_interactions(ctx: RunContextWrapper):
    """
    Herramienta que guarda las últimas interacciones en Redis para contexto futuro.
    """
    try:
        user_id = ctx.context.get("userID")
        last_interactions= get_last_interactions_summary(user_id)
        if not last_interactions:
            print("No se encontraron interacciones pasadas.")
            return "No se encontraron interacciones pasadas."
        else:
            return last_interactions
    except Exception as e:
        print(f"[ERROR] remember_last_interactions: {e}")
        return "Error al recuperar interacciones pasadas."
    
    