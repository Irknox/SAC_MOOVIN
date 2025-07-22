from agents import function_tool
import os
import psycopg2
from openai import OpenAI
from psycopg2.extras import Json
from database_handler import get_delivery_date, get_package_historic, get_id_package
from mcp_handler import create_pickup_ticket


## ------------------ MCP Tools ------------------ ##
def Make_request_to_pickup_tool(pool):
    @function_tool(
        name_override="pickup_ticket",
        description_override="Crea un ticket de recogida para un paquete a partir de su Tracking o numero de seguimiento"
    )
    async def pickup_ticket(package: str) -> dict:
        print(f"🛠️ Creando ticket de recogida para {package}...")
        timeline = await get_package_historic(pool, package)
        if timeline and str(timeline[0].get("status", "")).upper() in {"DELIVERED", "DELIVEREDCOMPLETE"}:
            return {
                "tracking": package,
                "package_found": True,
                "response": "Paquete ya fue entregado"}
        else: 
            return {"status": "success", "message": f"Created Pickup ticket  for {package}"}

    return pickup_ticket