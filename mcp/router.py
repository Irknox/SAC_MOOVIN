from mcp.handlers import create_ticket, notify_human


def run_mcp(input: dict) -> str:
    """
    Punto de entrada del MCP. Recibe un dict con una acción y datos.
    """
    action = input.get("action")

    if action == "create_ticket":
        return create_ticket(input.get("data", {}))
    elif action == "notify_human":
        return notify_human(input.get("data", {}))
    else:
        return f"[MCP] Acción desconocida: {action}"