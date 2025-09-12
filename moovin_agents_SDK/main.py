from __future__ import annotations as _annotations
import json
import random
import string
import os
from pydantic import BaseModel,Field
from agents import (
    Agent,
    handoff,
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
from typing import Optional, Dict, Any

load_dotenv()

# =========================
# CONTEXT
# =========================

class MoovinAgentContext(BaseModel):
    user_id: str | None = None
    package_id: str | None = None
    issued_tickets_info: list[dict] = Field(default_factory=list) 
    user_env: dict | None = None
    imgs_ids: list[int] | None = None
    location_sent: dict | None = None
    input_tripwired_trigered_reason: str | None = None
    output_tripwired_trigered_reason: Optional[str] = None
    backup_memory_called:bool | None = None
    handoff_from: Optional[str] = None
    handoff_to: Optional[str] = None
    handoff_reason: Optional[str] = None
    
    
def create_initial_context() -> MoovinAgentContext:
    return MoovinAgentContext(user_id=str(random.randint(10000, 99999)))


class MessageOutput(BaseModel):
    response: str


# =========================
# ON HANDOFF
# =========================
def record_railing_handoff(target_agent_name: str):
    def _on_handoff(ctx: RunContextWrapper[MoovinAgentContext]):
        reason = (ctx.context.input_tripwired_trigered_reason or "").strip()
        ctx.context.handoff_from = "Railing Agent"
        ctx.context.handoff_to = target_agent_name
        ctx.context.handoff_reason = reason or "Sin razón especificada"
    return _on_handoff

def on_raling_agent_handoff(ctx: RunContextWrapper[MoovinAgentContext]):
    output_tripwired_reason = (
        f"Esta consulta te llega porque el Railing Agent ha decidido que es necesario redirigir la consulta a ti por la siguiente razon: {ctx.context.output_tripwired_trigered_reason}"
        f"\n\n"
        f"Reformula tu respuesta si es necesario, o actua de acuerdo a lo indicado en tu prompt y la razon por la que el guardarail fue activado."
        )
    ctx.context.output_tripwired_trigered_reason = output_tripwired_reason
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
    
    El guardarailes NO debe activarse si:
        - Es una consulta general.
        - La consulta no esta especificamente dentro de las capacidades de alguno de los agentes especializados.
        
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

async def build_agents(tools_pool,mysql_pool,prompts):     
    ##--------Instrucciones--------##               
    def input_guardrail_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        return (
            f"{prompts["Input"]}\n"
            "Respondes con un reasoning:str=Motivo por el cual se activo o no el guardarail, passed:bool=en true si la respuesta del agente es correcta, false si la respuesta no es correcta"
        )
        
    def output_guardrail_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
            return (
            f"{prompts["Output"]}\n"
            "Respondes con un reasoning:str=Motivo por el cual se activo o no el guardarail, passed:bool=en true si la respuesta del agente es correcta, false si la respuesta no es correcta"
            )
                

    def general_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        debug_context_info(ctx, label="General Agent")  
        env_info = ""
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{prompts["General Prompt"]}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{prompts["General Agent"]}\n"
        )
        
    def package_analysis_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        env_info = f"\nUser data:\n{ctx.context.user_env}" if ctx.context.user_env else ""
        note = ""
        if ctx.context.handoff_to == agent.name and ctx.context.handoff_from == "Railing Agent" and ctx.context.output_tripwired_trigered_reason!= None:
            if ctx.context.handoff_reason:
                note = (
                    "\n\n[Handoff del Railing Agent] Motivo: "
                    f"{ctx.context.handoff_reason}\nAjusta tu respuesta a esta razón."
                )
                
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{prompts["General Prompt"]}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{prompts["Package Analyst Agent"]}\n"
            f"{note}"
        )

    def mcp_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        env_info = f"\nUser data:\n{ctx.context.user_env}" if ctx.context.user_env else ""
        note = ""
        if ctx.context.handoff_to == agent.name and ctx.context.handoff_from == "Railing Agent" and ctx.context.output_tripwired_trigered_reason!= None:
            if ctx.context.handoff_reason:
                note = (
                    "\n\n[Handoff del Railing Agent] Motivo: "
                    f"{ctx.context.handoff_reason}\nResuelve directo y evita meta‑comentarios."
                )
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{prompts["MCP Agent"]}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{prompts["General Prompt"]}\n"
            f"{note}"
        )
        
    def railing_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        debug_context_info(ctx, label="Railing agent")  
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{prompts["General Prompt"]}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{prompts["Railing Agent"]}\n"
            f"Razon por la que el tripwire fue activado, razonamiento del guardrailes: {ctx.context.input_tripwired_trigered_reason}"
        )
    ##--------Instrucciones--------##        
        
    ##--------Guardarailes--------##
    input_guardrail_agent = Agent[MoovinAgentContext](
        name="Input Guardrail Agent",
        model="gpt-4o-mini",
        instructions=input_guardrail_instructions,
        output_type=BasicGuardrailOutput,
    )

    output_guardrail_agent = Agent[MoovinAgentContext](
        name="Output Guardrail Agent",
        model="gpt-4o-mini",
        instructions=output_guardrail_instructions,
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
    ##--------Guardarailes--------##
    
    ##--------Agentes--------##        
    mcp_agent = Agent[MoovinAgentContext](
        name="MCP Agent",
        model="gpt-4o-mini",
        instructions=mcp_agent_instructions,
        tools=[Make_remember_tool(mysql_pool),Make_request_to_pickup_tool(tools_pool),Make_request_electronic_receipt_tool(tools_pool),Make_package_damaged_tool(mysql_pool,tools_pool),Make_send_current_delivery_address_tool(tools_pool), Make_send_delivery_address_requested_tool(),Make_change_delivery_address_tool(tools_pool)],
        input_guardrails=[basic_guardrail,emotional_analyst],
        output_type=MessageOutput
    )
    
    package_analysis_agent = Agent[MoovinAgentContext](
        name="Package Analysis Agent",
        model="gpt-4o-mini",
        instructions=package_analysis_instructions,
        handoffs=[mcp_agent],
        tools=[Make_remember_tool(mysql_pool),make_get_package_timeline_tool(tools_pool),make_get_likely_package_timelines_tool(tools_pool),make_get_SLA_tool(tools_pool),Make_send_current_delivery_address_tool(tools_pool)],
        input_guardrails=[basic_guardrail,emotional_analyst],
        output_type=MessageOutput,
    
    )

    general_agent = Agent[MoovinAgentContext](
        name="General Agent",
        model="gpt-4o-mini",
        instructions=general_agent_instructions,
        tools=[Make_remember_tool(mysql_pool)],
        handoffs=[package_analysis_agent, mcp_agent],
        input_guardrails=[basic_guardrail, to_specialized_agent_guardrail, emotional_analyst], 
        output_type=MessageOutput,
    )
    
    handoff_to_mcp = handoff(
    agent=mcp_agent,
    on_handoff=record_railing_handoff("MCP Agent"),
    )

    handoff_to_package = handoff(
    agent=package_analysis_agent,
    on_handoff=record_railing_handoff("Package Analysis Agent"),
    )

    handoff_to_general = handoff(
    agent=general_agent,
    on_handoff=record_railing_handoff("General Agent"),
    )
    
    railing_agent = Agent[MoovinAgentContext](
        name="Railing Agent",
        model="gpt-4o-mini",
        instructions=railing_agent_instructions,
        tools=[Make_remember_tool(mysql_pool)],
        handoffs=[handoff_to_mcp, handoff_to_package, handoff_to_general],
        input_guardrails=[emotional_analyst],
        output_type=MessageOutput,
    )
        
    # Return handoffs
    package_analysis_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(package_analysis_agent)
    ##--------Agentes--------##        
    
    
    return general_agent, package_analysis_agent, mcp_agent,railing_agent, create_initial_context
