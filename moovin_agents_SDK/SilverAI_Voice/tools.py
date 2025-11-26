from agents import function_tool, RunContextWrapper
import os, asyncio, json
import requests


ARI_CONTROL_URL = os.getenv("ARI_CONTROL_URL", "http://127.0.0.1:8787")
ARI_CONTROL_TOKEN = os.getenv("ARI_CONTROL_TOKEN")

@function_tool(
    name_override="escalate_call",
    description_override="Escala inmediatamente a un asistente Humano. Úsala ÚNICAMENTE cuando el usuario solicite hablar con un Humano."
)
async def escalate_call(call_id: str, target_ext: int = 9999, mode: str = "dialplan"):
    if not ARI_CONTROL_TOKEN:
        return {"status": "error", "reason": "missing ARI_CONTROL_TOKEN"}

    url = ARI_CONTROL_URL.rstrip("/") + "/transfer"
    payload = {"call_id": call_id, "target_ext": int(target_ext), "mode": mode}
    headers = {
        "x-ari-control-token": ARI_CONTROL_TOKEN,
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

        if resp.ok:
            return data  
        return {"status": "error", "http_status": resp.status_code, "response": data}
    except Exception as e:
        return {"status": "error", "reason": "request_failed", "detail": repr(e)}
