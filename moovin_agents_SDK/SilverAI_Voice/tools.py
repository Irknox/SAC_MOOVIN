from agents import function_tool, RunContextWrapper
import os, socket, asyncio
import psycopg2
from openai import OpenAI
from psycopg2.extras import Json
from dotenv import load_dotenv
ARI_CONTROL_HOST = os.getenv("ARI_CONTROL_HOST")
ARI_CONTROL_PORT = int(os.getenv("ARI_CONTROL_PORT"))
CONTROL_TOKEN    = os.getenv("CONTROL_TOKEN")

@function_tool(
        name_override="escalate_call",
        description_override="Escala inmediatamente a un asistente Humano, usala esta herramienta UNICAMENTE cuando un usuario solicite hablar con un Humano"
)
async def escalate_call(target_ext: int = 2121, context: str = "from-internal"):
    """
    Solicita al ARI transferir la llamada actual a otra extensión del mismo PBX.
    Retorna dict con 'ok' booleano.
    """
    msg = None
    if CONTROL_TOKEN:
        msg = f"XFER {CONTROL_TOKEN} {target_ext} {context}".encode("utf-8")
    else:
        return {
            "status":"error",
            "reason":"missing internal arguments"
        }
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(msg, (ARI_CONTROL_HOST, ARI_CONTROL_PORT))
    finally:
        try: sock.close()
        except: pass
    return {"ok": True, "ext": str(target_ext), "context": context}