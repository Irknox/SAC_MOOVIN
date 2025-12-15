from agents import function_tool, RunContextWrapper
import os, asyncio, json
import requests
from SilverAI_Brain.brain import BrainRunner, BrainContext
from pydantic import BaseModel, Field


ARI_CONTROL_URL = os.getenv("ARI_CONTROL_URL")
AMI_CONTROL_TOKEN = os.getenv("AMI_CONTROL_TOKEN")

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

class ThinkInput(BaseModel):
    query: str = Field(description="La pregunta o solicitud completa del usuario que SilverAI no puede responder sin la lógica especializada.")


def Make_think_tool(call_id: str, brain_runner: BrainRunner):
    """
    Función fábrica que crea y devuelve una instancia de la herramienta 'think' 
    con las variables call_id y brain_runner encapsuladas (closure).
    """
    from agents import TResponseInputItem
    from agents.agent import ToolsToFinalOutputResult
    @function_tool(
        name_override="think",
        description_override="Has una consulta especializada a un sistema de agentes multi-nodo para responder preguntas complejas sobre rastreo, tarifas, ubicaciones, etc."
    )
    async def think(query: str) -> str:
        """
        Usa el sistema de agentes especializados de Moovin para responder a consultas complejas de rastreo, 
        tarifas, ubicaciones, etc. Devuelve la respuesta final para que SilverAI la diga.
        """

        print(f"Pensando 🧠...{query}")
        try:
            if not brain_runner:
                print("[DEBUG-ERROR] Brain Runner no está inicializado")
                return "Error interno: El sistema especializado (Brain) no está inicializado."
            print(f"Llego aqui!!!")
            input_item = TResponseInputItem(user={"text": query})
            brain_context = BrainContext(session_id=call_id, call_id=call_id) 
            result: ToolsToFinalOutputResult = await brain_runner.execute_query([input_item], brain_context)
            print(f"Resultado del sistema especializado: {result}")
            if result.final_output and result.final_output.get("text"):
                return result.final_output["text"]
            print("[DEBUG-ERROR] El sistema especializado completó la tarea, pero no pudo generar una respuesta de texto.")
            return "El sistema especializado completó la tarea, pero no pudo generar una respuesta de texto."
        except Exception as e:
            print(f"[ERROR] Error al ejecutar la herramienta 'think' de SilverAI: {e}")
            return "Disculpe, la base de conocimiento especializada experimentó un fallo. Por favor, intente reformular la pregunta."
        
    return think