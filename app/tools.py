from langchain.tools import tool

@tool(description="Repite el texto recibido como input")
def echo_tool(input_text: str) -> str:
    return f"ECHO: {input_text}"

# Lista de tools
TOOLS = [echo_tool]