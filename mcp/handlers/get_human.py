def notify_human(data: dict) -> str:
    razon = data.get("razon", "sin razón especificada")
    return f"[MCP] Se notificó a un humano: {razon}"
