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
    input_guardrail,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from tools import make_get_package_timeline_tool, make_get_SLA_tool,make_get_likely_package_timelines_tool
from dotenv import load_dotenv
from mcp_handler import init_mcp_servers

import asyncio


load_dotenv()

# =========================
# CONTEXT
# =========================

class MoovinAgentContext(BaseModel):
    user_id: str | None = None
    package_id: str | None = None
    issue_ticket_id: str | None = None
    user_env: dict | None = None
    
def create_initial_context() -> MoovinAgentContext:
    return MoovinAgentContext(user_id=str(random.randint(10000, 99999)))

# =========================
# GUARDRAILS
# =========================

class BasicGuardrailOutput(BaseModel):
    reasoning: str
    passed: bool

basic_guardrail_agent = Agent(
    model="gpt-4o",
    name="Basic Guardrail Agent",
    instructions="Evaluate whether the input message is appropriate for logistics support.",
    output_type=BasicGuardrailOutput,
)




@input_guardrail(name="Basic Relevance Check")
async def basic_guardrail(
    context: RunContextWrapper[MoovinAgentContext], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(basic_guardrail_agent, input, context=context.context)
    final = result.final_output_as(BasicGuardrailOutput)

    if not final.passed:
        redirection_message = (
            "😅 Parece que tu pregunta no está relacionada con envíos o logística. "
            "¿Te gustaría saber el estado de un paquete, los tiempos de entrega o crear un ticket de soporte? "
            "¡Estoy aquí para ayudarte con todo lo relacionado a Moovin!"
        )
        return GuardrailFunctionOutput(
            output_info=final,
            tripwire_triggered=True,
            response_override=redirection_message
        )

    return GuardrailFunctionOutput(output_info=final, tripwire_triggered=False)




# =========================
# MCPs
# =========================



# =========================
# AGENTES
# =========================

async def build_agents(tools_pool):
    with open(os.path.join(os.path.dirname(__file__), "prompts", "general_prompt.txt"), "r", encoding="utf-8") as f:
        GENERAL_PROMPT = f.read()
    with open(os.path.join(os.path.dirname(__file__), "prompts", "package_analyst.txt"), "r", encoding="utf-8") as f:
        PACKAGE_ANALYST_PROMPT = f.read()
    with open(os.path.join(os.path.dirname(__file__), "prompts", "general_agent.txt"), "r", encoding="utf-8") as f:
        GENERAL_AGENT_PROMPT = f.read()   
        
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


    package_analysis_agent = Agent[MoovinAgentContext](
        name="Package Analysis Agent",
        model="gpt-4o-mini",
        instructions=package_analysis_instructions,
        tools=[make_get_package_timeline_tool(tools_pool),make_get_likely_package_timelines_tool(tools_pool),make_get_SLA_tool(tools_pool)],
        mcp_servers={}, 
        input_guardrails=[],
    )

    general_agent = Agent[MoovinAgentContext](
        name="General Agent",
        model="gpt-4o-mini",
        instructions=general_agent_instructions,
        handoffs=[package_analysis_agent],
        input_guardrails=[],
    )

    # Return handoffs
    package_analysis_agent.handoffs.append(general_agent)

    return general_agent, package_analysis_agent,create_initial_context
