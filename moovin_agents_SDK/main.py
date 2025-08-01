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
from tools import make_get_package_timeline_tool, make_get_SLA_tool,make_get_likely_package_timelines_tool
from dotenv import load_dotenv
from mcp_tools import Make_request_to_pickup_tool,Make_request_electronic_receipt_tool,Make_package_damaged_tool


#---------------------- Prompts ----------------------#
with open(os.path.join(os.path.dirname(__file__), "prompts", "general_prompt.txt"), "r", encoding="utf-8") as f:
        GENERAL_PROMPT = f.read()
with open(os.path.join(os.path.dirname(__file__), "prompts", "package_analyst.txt"), "r", encoding="utf-8") as f:
        PACKAGE_ANALYST_PROMPT = f.read()
with open(os.path.join(os.path.dirname(__file__), "prompts", "general_agent.txt"), "r", encoding="utf-8") as f:
        GENERAL_AGENT_PROMPT = f.read()
with open(os.path.join(os.path.dirname(__file__), "prompts", "mcp_agent.txt"), "r", encoding="utf-8") as f:
        MCP_AGENT_PROMPT = f.read()  

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


input_guardrail_agent = Agent[MoovinAgentContext](
    name="Input Guardrail Agent",
    model="gpt-4o-mini",
    instructions="""
        Evalua si la entrada es relevante para el flujo de trabajo actual.
        Si la entrada indica que recibiste una imagen, esta es relevante para el flujo actual, no debe activarse el guardariales en estos casos
        Si es relevante y puede ser atendida, devuelve 'true' y una breve explicación. 
        Si no es relevante, devuelve 'false' y una breve explicación. 
        
        Contexto general sobre el flujo actual: 

        """ + GENERAL_PROMPT,
    output_type=BasicGuardrailOutput,
)


@input_guardrail(name="Basic Relevance Check")
async def basic_guardrail(
    context: RunContextWrapper[MoovinAgentContext], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(input_guardrail_agent, input, context=context.context)
    final = result.final_output_as(BasicGuardrailOutput)
    print (f"🚦 Resultado del guardarailes: {final}")
    if not final.passed:
        print(f"⚠️ Tripwire activado, razon de guardarailes: {final.reasoning}")
        return GuardrailFunctionOutput(
            output_info=final,
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(output_info=final, tripwire_triggered=False)

def debug_context_info(ctx: RunContextWrapper[MoovinAgentContext], label: str = ""):
    print(f"🔍 {label} Contexto del agente:{ctx}")
    if ctx.context.imgs_ids:
        print(f"🖼️ {label} Imágenes en contexto: {ctx.context.imgs_ids}")
    if ctx.context.user_env:
        print(f"👤 {label} Datos del usuario: {ctx.context.user_env}")

# =========================
# AGENTES
# =========================

async def build_agents(tools_pool,mysql_pool):

    def general_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        env_info = ""
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"{GENERAL_AGENT_PROMPT}\n"
        )
        
    def package_analysis_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        env_info = ""
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"{PACKAGE_ANALYST_PROMPT}\n"
        )
        
    def mcp_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        env_info = ""
        if ctx.context.user_env:
            env_info = f"\nUser data:\n{ctx.context.user_env}"
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{GENERAL_PROMPT}\n"
            f"Datos precargados para este usuario: {env_info}\n"
            f"{MCP_AGENT_PROMPT}\n"
        )
    def railing_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
        return (
            f"{RECOMMENDED_PROMPT_PREFIX}\n"
            f"{GENERAL_PROMPT} "
            "##Rol: Tu deber es tomar la entrada de un usuario que no esta dentro de lo deseado para el flujo o se alinean con nuestros idealos y redirigir la conversacion hacia la gestion.\n\n "
            "##Detalles especificos:\n\n"
            "- Basado en el contexto general, si la entrada del usuario no es relevante para el flujo de trabajo actual, redirige al usuario a una consulta o gestion adecuada.\n"
            "- Para redirigir al usuario se sarcastico, puedes usar humor, siempre siendo respetuoso pero buscando el engage.\n"
            "- Nunca abordes temas polemicos o que puedan ser malinterpretados, siempre redirige a la gestion. Evita teorias de conspiracion, rumores, etc \n"
            "##Notas:\n\n"
            "- No menciones que lo que dicen es conspiracion, ni nada por el estilo, se bastante sarcastico pero redirige la conversacion sin mencionar o dar pistas del por que.\n"
            "- Una burla sutil o un comentario sarcastico puede ser efectivo, pero siempre redirige la conversacion a la gestion.\n" 
        )
        
    mcp_agent = Agent[MoovinAgentContext](
        name="MCP Agent",
        model="gpt-4o-mini",
        instructions=mcp_agent_instructions,
        tools=[Make_request_to_pickup_tool(tools_pool),Make_request_electronic_receipt_tool(tools_pool),Make_package_damaged_tool(mysql_pool,tools_pool)],
        input_guardrails=[],
    
    )
    
    package_analysis_agent = Agent[MoovinAgentContext](
        name="Package Analysis Agent",
        model="gpt-4o-mini",
        instructions=package_analysis_instructions,
        handoffs=[mcp_agent],
        tools=[make_get_package_timeline_tool(tools_pool),make_get_likely_package_timelines_tool(tools_pool),make_get_SLA_tool(tools_pool)],
        input_guardrails=[],
    
    )

    general_agent = Agent[MoovinAgentContext](
        name="General Agent",
        model="gpt-4o-mini",
        instructions=general_agent_instructions,
        handoffs=[package_analysis_agent,mcp_agent],
        input_guardrails=[],    
    )
    
    railing_agent = Agent[MoovinAgentContext](
    name="Railing Agent",
    model="gpt-4o-mini",
    instructions=railing_agent_instructions,
    tools=[],
    handoffs=[mcp_agent, package_analysis_agent, general_agent],
    input_guardrails=[],
    )
    
    
    # Return handoffs
    package_analysis_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(general_agent)
    mcp_agent.handoffs.append(package_analysis_agent)

    return general_agent, package_analysis_agent, mcp_agent,railing_agent, create_initial_context
