from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain.tools import tool
import os
from mcp.tools.create_ticket import create_ticket
from mcp.tools.change_delivery_address import change_delivery_address



@tool(description="Crea un ticket con la información proporcionada.")
def create_ticket(data: str) -> str:
    return f"Ticket created"

@tool(description="Cambia la direccion de entrega de un paquete dada un motivo y coordenadas en latitud y longitd.")
def change_delivery_address(data: str) -> str:
    return f"Delivery address changed"

MCP_TOOLS = [create_ticket, change_delivery_address]

# Prompt para el MCP
MCP_PROMPT = PromptTemplate.from_template("""
Eres un agente MCP, recibes instrucciones de otro agente AI cuando se debe interactuar con algun aplicacion exterior,
tu rol es basado en las instrucciones que te de el agente, decidir que herramienta debes usar y como debes interactuar con ella, una vez obtienes la respuesta de la herramineta informas al agente central el estado de la solicitud

Para crear un ticket el debes tener un correo, una explicacion o motivo y un tracking o numero de seguimiento.

##Herramientas disponibles:
    - `create_ticket`: Crea un ticket con la información proporcionada y responde con "Ticket created" en caso de ser exitoso, si no informa del error.
    - `change_delivery_address`: Cambia la direccion de entrega dado un motivo y direccion en formato latitud y longitud, responde con "Delivery address changed" en caso de ser exitoso, si no informa del error.

##Detalles Especificos 
    -Una vez obtengas la respuesta de la herramienta, debes informar al agente central el estado de la solicitud (Si se realizo con exito o no)
    -No uses las herramientas si no es necesario, solo si el agente central te lo indica.

##Notas
    -Al responder al agente central, se breve, ejemplo: "Ticket creado con éxito, informa al Usuario" o "Notificación enviada al humano, informa al Usuario".
    -No uses la misma herramienta reiteradamente con la misma solicitud si ya fue usada con exito.

Mensaje del agente principal con instrucciones: {input}
{agent_scratchpad}
""")


OPENAI_API_KEY = os.environ.get("OPEN_AI_API")
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model="gpt-4o")##
agent = create_openai_functions_agent(llm=llm, tools=MCP_TOOLS, prompt=MCP_PROMPT)
agent_executor = AgentExecutor(agent=agent, tools=MCP_TOOLS, verbose=True)

def run_mcp(user_message: str) -> str:
    """
    Punto de entrada del MCP. Recibe un string con la instrucción del usuario.
    """
    result = agent_executor.invoke({"input": user_message})
    return result["output"] if "output" in result else str(result)