from langchain.tools import tool


@tool(description="Obtiene el estado de un paquete dado su ID")
def get_package_status(package_id: str) -> str:
    """
    Simula la obtención del estado de un paquete.
    En un caso real, aquí se haría una llamada a una API externa.
    """
    return f"Estado del paquete {package_id}: En tránsito"

# Lista de tools
TOOLS = [ get_package_status]