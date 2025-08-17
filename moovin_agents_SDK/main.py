from __future__ import annotations as _annotations
import json
import random
import string
import os
from pydantic import BaseModel
from agents import (
    Agent,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    GuardrailFunctionOutput,
    input_guardrail,output_guardrail
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from tools import Make_remember_tool,make_get_package_timeline_tool, make_get_SLA_tool,make_get_likely_package_timelines_tool, Make_send_current_delivery_address_tool
from dotenv import load_dotenv
from mcp_tools import Make_request_to_pickup_tool,Make_request_electronic_receipt_tool,Make_package_damaged_tool, Make_send_delivery_address_requested_tool,Make_change_delivery_address_tool


#---------------------- Prompts ----------------------#
with open(os.path.join(os.path.dirname(__file__), "prompts", "general_prompt.txt"), "r", encoding="utf-8") as f:
        GENERAL_PROMPT = f.read()
with open(os.path.join(os.path.dirname(__file__), "prompts", "package_analyst.txt"), "r", encoding="utf-8") as f:
        PACKAGE_ANALYST_PROMPT = f.read()
with open(os.path.join(os.path.dirname(__file__), "prompts", "general_agent.txt"), "r", encoding="utf-8") as f:
        GENERAL_AGENT_PROMPT = f.read()
with open(os.path.join(os.path.dirname(__file__), "prompts", "mcp_agent.txt"), "r", encoding="utf-8") as f:
        MCP_AGENT_PROMPT = f.read()  
with open(os.path.join(os.path.dirname(__file__), "prompts", "railing_agent.txt"), "r", encoding="utf-8") as f:
       RAILING_AGENT_PROMPT = f.read()  
with open(os.path.join(os.path.dirname(__file__), "prompts", "input_guardrail_prompt.txt"), "r", encoding="utf-8") as f:
       INPUT_GUARDRAIL_PROMPT = f.read()  

load_dotenv()

# =========================
# CONTEXT
# =========================

class MoovinAgentContext(BaseModel):
    user_id: str | None = None
    package_id: str | None = None
    issue_ticket_id: str | None = None
    user_env: dict | None = None
    imgs_ids: list[int] | None = None
    location_sent: dict | None = None
    tripwired_trigered_reason: str | None = None
    backup_memory_called:bool | None = None

    
    
def create_initial_context() -> MoovinAgentContext:
    return MoovinAgentContext(user_id=str(random.randint(10000, 99999)))


class MessageOutput(BaseModel):
    response: str


# =========================
# GUARDRAILS
# =========================

class BasicGuardrailOutput(BaseModel):
    reasoning: str
    passed: bool
    
class EmotionalAgentOutput(BaseModel):
    user_emotional_state: str
    reasoning: str
    
class RoutingGuardrailOutput(BaseModel):
    reasoning: str
    correct_agent: str
    passed: bool
    
def input_guardrail_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        return (
            f"{INPUT_GUARDRAIL_PROMPT}\n"
        )
        
    
input_guardrail_agent = Agent[MoovinAgentContext](
    name="Input Guardrail Agent",
    model="gpt-4o-mini",
    instructions=input_guardrail_instructions,
    output_type=BasicGuardrailOutput,
)


output_guardrail_agent = Agent[MoovinAgentContext](
    name="Output Guardrail Agent",
    model="gpt-4o-mini",
    instructions= """
    Guardarail que verifica si la respuesta del agente es apta basandote en varias reglas de comportamiento.
    
    Reglas de comportamiento:
        -Los agentes no deben hacer mencion a la existencia de Agentes diferentes a Agente AI Moovin, informacion relacionada al SDK o sistema.
        -Los agentes no deben decir "Te voy a comunicar con x agente" o hacer referencia a la existencia de otros agentes.
        -El flujo natural de la conversacion es necesaria, por eso los agentes no deben responder cosas como, voy a usar x herramienta o voy a proceder la solicitud y, en cambio, deben realizarlo e informar al usuario.
        -Los agentes no deberian contestar cosas como, "Te mantendré informado sobre el progreso" o "Dame un minuto para x cosa por" ejemplo, es necesario que cada mensaje del agente lleve informacion de valor, mensajes indicando pasos faltantes no son validos como respuesta y DEBEN activar el guardarail.
        -Los agentes no deben entrar en temas de conspiracion, politicos, religiosos o que puedan generar un impacto negativo en la imagen de la empresa.
        
    - El sarcasmo es valido, los agentes pueden hacer uso de el al mencionar temas politicos, religiosos o problematicos a la hora de redireccionar la conversacion, si este es el caso el guardarail NO debe activarse.  
    Respondes con un reasoning:str=Motivo por el cual se activo o no el guardarail, passed:bool=en true si la respuesta del agente es correcta, false si la respuesta no es correcta
    """,
    output_type=BasicGuardrailOutput,
)

@input_guardrail(name="Basic Relevance Check")
async def basic_guardrail(
    context: RunContextWrapper[MoovinAgentContext], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(input_guardrail_agent, input, context=context.context)
    final = result.final_output_as(BasicGuardrailOutput)
    if not final.passed:
        return GuardrailFunctionOutput(
            output_info=final,
            tripwire_triggered=True,
        )
    return GuardrailFunctionOutput(output_info=final, tripwire_triggered=False)

@output_guardrail(name="Basic Output Guardrail")
async def basic_output_guardrail(
    ctx:RunContextWrapper[MoovinAgentContext], agent: Agent, output: MessageOutput
 )-> GuardrailFunctionOutput:
        output_dict = output.response
        result = await Runner.run(output_guardrail_agent, output.response, context=ctx.context)
        final = result.final_output_as(BasicGuardrailOutput)
        if not final.passed:
            print (f"Y este es el output que recibio:  {output_dict}")
        return GuardrailFunctionOutput(
            output_info=final,
            tripwire_triggered=not final.passed,
        )

##----------------------------Guardrailes Auxiliares----------------------------##

to_specialized_agent = Agent[MoovinAgentContext](
    name="To Specialized Agent",
    model="gpt-4o-mini",
    instructions="""
    ##Tarea: Valida si la solicitud del usuario esta dentro de las capacidades de alguno de estos agentes, si lo esta, el guardarailes debe activarse.
    
    Package Analysis Agent:
    - Encargado de todas las consultas relacionadas con paquetes: donde esta mi paquete, que ha pasado, cuando llegará.
        - Puede consultar informacion sobre los paquetes del usuario.
        - Envia la direccion de entrega actual o donde fue entregado el paquete al usuario.
        - Puede conocer la tienda donde se compro.

    MCP Agent:
    - Agente encargado de ejecutar acciones en aplicaciones externas, Encargado de manejar las siguientes solicitudes.
        - Capacidades:
            - Crear Ticket para solicitud de recoleccion en sede Moovin.
            - Cambiar la direccion de entrega de un paquete.
            - Solicitud de Factura electronica por los impuestos pagados.
            - Crear Ticket para reporte de paquete dañado.
            - Trabajar con Moovin
                - Aun no disponible
            - Comprar Empaques
                - Aun no disponible
            Este agente *NO* contacta con servicio al cliente ni es una manera para llegar a ellos.
    
    
    - Respondes con reasoning: str=Explicacion del por que el resultado, correct_agent: str=Nombre del agente que debe realizar la atencion y passed: booleano, en true si se activa, false si no.
    """,
    output_type=RoutingGuardrailOutput,
)

emotional_analyst_agent=Agent[MoovinAgentContext](
    name="Emotional Analyst",
    model="gpt-4o-mini",
    instructions="""
    ##Tarea: Tu deber es analizar el mensaje del usuario y el estado actual de la conversacion y definir el estado emocional actual del usuario basado unicamente en su actitud.
    
    Aunque el usuario haya experimentado situaciones no deseadas, esto no quiere indicar que su estado emocional se vio afectado, basate unicamente en la actitud del usuario para definir su estado emocional.
    
    Para esto lo divides en 3 estados:
        -Satisfecho (Muestra satisfaccion con la asistencia)
        -Normal (No hay indicios reales de satisfaccion o enojo)
        -Molesto (El usuario expresa su malestar)
    
    Respondes con el estado emocional actual y un razonamiento del por que tu decision.
    El guardarailes no debe activarse nunca, solo analiza el estado emocional del usuario.
    """,
    output_type=EmotionalAgentOutput,
)

@input_guardrail(name="Emotional Analyst")
async def emotional_analyst(
    ctx: RunContextWrapper[MoovinAgentContext], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(emotional_analyst_agent, input, context=ctx.context)
    final = result.final_output_as(EmotionalAgentOutput)
    ctx.context.user_env["emotional_state"]=final.user_emotional_state
    return GuardrailFunctionOutput(output_info=final, tripwire_triggered=False)


@input_guardrail(name="To Specialized Agent")
async def to_specialized_agent_guardrail(
    context: RunContextWrapper[MoovinAgentContext], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(to_specialized_agent, input, context=context.context)
    final = result.final_output_as(RoutingGuardrailOutput)
    if  final.passed:
        return GuardrailFunctionOutput(
            output_info=final,
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(output_info=final, tripwire_triggered=False)




def debug_context_info(ctx: RunContextWrapper[MoovinAgentContext], label: str = ""):
    return
    print(f"Se cargo el agente {label}")
    print(f"🔍Contexto del agente:{ctx.context}")
    if ctx.context.imgs_ids:
        print(f"🖼️ {label} Imágenes en contexto: {ctx.context.imgs_ids}")

# =========================
# AGENTES
# =========================

async def build_agents(tools_pool,mysql_pool):

    def general_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        debug_context_info(ctx, label="General Agent")  
        env_info = ""
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{GENERAL_AGENT_PROMPT}\n"
        )
        
    def package_analysis_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        debug_context_info(ctx, label="Package Analyst Agent")  
        env_info = ""
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n" 
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{PACKAGE_ANALYST_PROMPT}\n"
        )
        
    def mcp_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        debug_context_info(ctx, label="MCP Agent")  
        env_info = ""
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{MCP_AGENT_PROMPT}\n"
        )
        
    def railing_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        debug_context_info(ctx, label="Railing agent")  
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{RAILING_AGENT_PROMPT}\n"  
            f"Razon por la que el tripwire fue activado, razonamiento del guardrailes: {ctx.context.tripwired_trigered_reason}"
        )
        
    mcp_agent = Agent[MoovinAgentContext](
        name="MCP Agent",
        model="gpt-4o-mini",
        instructions=mcp_agent_instructions,
        tools=[Make_remember_tool(mysql_pool),Make_request_to_pickup_tool(tools_pool),Make_request_electronic_receipt_tool(tools_pool),Make_package_damaged_tool(mysql_pool,tools_pool),Make_send_current_delivery_address_tool(tools_pool), Make_send_delivery_address_requested_tool(),Make_change_delivery_address_tool(tools_pool)],
        input_guardrails=[basic_guardrail,emotional_analyst],
        output_guardrails=[basic_output_guardrail],
        output_type=MessageOutput
    )
    
    package_analysis_agent = Agent[MoovinAgentContext](
        name="Package Analysis Agent",
        model="gpt-4o-mini",
        instructions=package_analysis_instructions,
        handoffs=[mcp_agent],
        tools=[Make_remember_tool(mysql_pool),make_get_package_timeline_tool(tools_pool),make_get_likely_package_timelines_tool(tools_pool),make_get_SLA_tool(tools_pool),Make_send_current_delivery_address_tool(tools_pool)],
        input_guardrails=[basic_guardrail,emotional_analyst],
        output_guardrails=[basic_output_guardrail],
        output_type=MessageOutput,
    
    )

    general_agent = Agent[MoovinAgentContext](
        name="General Agent",
        model="gpt-4o-mini",
        instructions=general_agent_instructions,
        tools=[Make_remember_tool(mysql_pool)],
        handoffs=[package_analysis_agent, mcp_agent],
        input_guardrails=[basic_guardrail, to_specialized_agent_guardrail, emotional_analyst], 
        output_guardrails=[basic_output_guardrail],
        output_type=MessageOutput,
    )
    
    railing_agent = Agent[MoovinAgentContext](
        name="Railing Agent",
        model="gpt-4o-mini",
        instructions=railing_agent_instructions,
        tools=[Make_remember_tool(mysql_pool)],
        handoffs=[mcp_agent, package_analysis_agent, general_agent],
        input_guardrails=[emotional_analyst],
        output_guardrails=[basic_output_guardrail],
        output_type=MessageOutput,
    )
    
    
    # Return handoffs
    package_analysis_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(package_analysis_agent)

    return general_agent, package_analysis_agent, mcp_agent,railing_agent, create_initial_context
