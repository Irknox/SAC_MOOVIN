from agents.tool import function_tool

@function_tool
async def create_ticket(reason: str, phone: str, email: str) -> str:
    """Crea un ticket de soporte con razón, teléfono y correo."""
    return f"Ticket creado con razón: {reason}, teléfono: {phone}, correo: {email}"
