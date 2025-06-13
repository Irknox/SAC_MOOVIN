def create_ticket(data: dict) -> str:
    usuario = data.get("usuario", "desconocido")
    asunto = data.get("asunto", "sin asunto")
    return f"[MCP] Ticket creado para {usuario} con asunto: '{asunto}'"
