from __future__ import annotations as _annotations

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
from tools import make_get_package_timeline_tool, make_get_SLA_tool,make_get_likely_package_timelines_tool, Make_send_current_delivery_address_tool
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
    current_agent: str | None = None

    
    
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
    
def input_guardrail_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        if ctx.context.current_agent:
            current_agent=ctx.context.current_agent
            print(f"Print del prompt del input de guardrail con el agente actual: {current_agent}")
        return (
            f"{INPUT_GUARDRAIL_PROMPT}\n"
                f"Guardrail actualmente en agente: {current_agent}"
        )
        
def output_guardrail_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        if ctx.context.current_agent:
            current_agent=ctx.context.current_agent
            print(f"Print del prompt del input de guardrail con el agente actual: {current_agent}")
        return (
            f"Guardrail actualmente en agente: {current_agent}"
            """
                Rol: Eres un Guardarail de Output.
                tarea: Recibes la respuesta de un agente en el flujo de agentes, tu deber es validar si esta respuesta es apta para el flujo actual.
                La respuesta debe ser evaluada con respecto al agente que la emitió.
                - El guardrail **nunca debe exigir un handoff hacia el mismo agente que está respondiendo**.
                
                El agente no debe:
                    -Dar informacion para la cual el usuario no haya verificado aun (Dar informacion del dueno de un paquete cuando el usuario no ha proporcionado el numero de paquete y telefono por ejemplo)
                    -Entrar en temas de conspiracion, politicos o que puedan ser perjudiciales para la imagen de una empresa. (Es posible que algun tema sea mencionado de manera muy sutil por que el usuario lo menciono, si es asi el Tripwire no debe activarse).            
                    - Mencionar cambios entre agentes o handoffs.
                    
                    Si la respuesta se encuentra detro de lo deseado, devuelve 'true' y una breve explicación. 
                    Si no es deseado, devuelve 'false' y una breve explicación.
                    
                Contexto general sobre el flujo actual: 
            """
            f"{GENERAL_PROMPT}"
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
    instructions= output_guardrail_instructions,
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
        print (f"Este es el agente en el output {agent.name}")
        print (f"Y este es el output que recibio:  {output}")
        result = await Runner.run(output_guardrail_agent, output.response, context=ctx.context)
        final = result.final_output_as(BasicGuardrailOutput)
        return GuardrailFunctionOutput(
            output_info=final,
            tripwire_triggered=not final.passed,
        )


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
            f"Contexto General sobre el SDK y Flujo de trabajo actual, instrucciones y demas..:\n" 
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
            f"Contexto General sobre el SDK y Flujo de trabajo actual, instrucciones y demas..:\n" 
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
            f"Contexto General sobre el SDK y Flujo de trabajo actual, instrucciones y demas..:\n" 
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
            f"Contexto General sobre el SDK y Flujo de trabajo actual, instrucciones y demas..:\n" 
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"System prompt para el agente actual:\n"
            f"{RAILING_AGENT_PROMPT}\n"  
            f"Razon por la que el triwire fue activado, razonamiento del guardrailes: {ctx.context.tripwired_trigered_reason}"
        )
        
    mcp_agent = Agent[MoovinAgentContext](
        name="MCP Agent",
        model="gpt-4o-mini",
        instructions=mcp_agent_instructions,
        tools=[Make_request_to_pickup_tool(tools_pool),Make_request_electronic_receipt_tool(tools_pool),Make_package_damaged_tool(mysql_pool,tools_pool),Make_send_current_delivery_address_tool(tools_pool), Make_send_delivery_address_requested_tool(),Make_change_delivery_address_tool(tools_pool)],
        input_guardrails=[basic_guardrail],
        output_type=MessageOutput
    )
    
    package_analysis_agent = Agent[MoovinAgentContext](
        name="Package Analysis Agent",
        model="gpt-4o-mini",
        instructions=package_analysis_instructions,
        handoffs=[mcp_agent],
        tools=[make_get_package_timeline_tool(tools_pool),make_get_likely_package_timelines_tool(tools_pool),make_get_SLA_tool(tools_pool),Make_send_current_delivery_address_tool(tools_pool)],
        input_guardrails=[basic_guardrail],
        output_type=MessageOutput,
    
    )

    general_agent = Agent[MoovinAgentContext](
        name="General Agent",
        model="gpt-4o-mini",
        instructions=general_agent_instructions,
        tools=[],
        handoffs=[package_analysis_agent, mcp_agent],
        input_guardrails=[basic_guardrail], 
        output_type=MessageOutput,
    )
    
    railing_agent = Agent[MoovinAgentContext](
        name="Railing Agent",
        model="gpt-4o-mini",
        instructions=railing_agent_instructions,
        tools=[],
        handoffs=[mcp_agent, package_analysis_agent, general_agent],
        input_guardrails=[],
        output_guardrails=[],
        output_type=MessageOutput,
    )
    
    
    # Return handoffs
    package_analysis_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(package_analysis_agent)

    return general_agent, package_analysis_agent, mcp_agent,railing_agent, create_initial_context
