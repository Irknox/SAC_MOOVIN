from agents import function_tool, RunContextWrapper
import os, asyncio, json
import requests
from agents import function_tool, RunContextWrapper

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
