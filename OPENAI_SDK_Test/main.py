# main.py
from __future__ import annotations as _annotations

import random
import string
from pydantic import BaseModel

from agents import (
    Agent,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    function_tool,
    handoff,
    GuardrailFunctionOutput,
    input_guardrail,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

# =========================
# CONTEXT
# =========================

class MoovinAgentContext(BaseModel):
    user_id: str | None = None
    package_id: str | None = None
    issue_ticket_id: str | None = None

def create_initial_context() -> MoovinAgentContext:
    return MoovinAgentContext(user_id=str(random.randint(10000, 99999)))

# =========================
# TOOLS
# =========================

@function_tool
def package_analysis_tool(package_id: str) -> str:
    return f"Package {package_id} has been analyzed and is currently in transit."

@function_tool
def create_ticket_tool(context: RunContextWrapper[MoovinAgentContext], description: str) -> str:
    ticket_id = "TCKT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    context.context.issue_ticket_id = ticket_id
    return f"Support ticket {ticket_id} created with description: '{description}'"

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
    context: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(basic_guardrail_agent, input, context=context.context)
    final = result.final_output_as(BasicGuardrailOutput)
    return GuardrailFunctionOutput(output_info=final, tripwire_triggered=not final.passed)

# =========================
# AGENTS
# =========================

def general_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
    return f"{RECOMMENDED_PROMPT_PREFIX}\nYou are a general assistant for Moovin logistics. Answer questions or redirect as needed."

def package_analysis_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
    return f"{RECOMMENDED_PROMPT_PREFIX}\nYou analyze package information and report the status of package {ctx.context.package_id or '[unknown]'}."

def ticketing_agent_instructions(ctx: RunContextWrapper[MoovinAgentContext], agent: Agent) -> str:
    return f"{RECOMMENDED_PROMPT_PREFIX}\nYou help customers create support tickets for logistics issues."

package_analysis_agent = Agent[MoovinAgentContext](
    name="Package Analysis Agent",
    model="gpt-4o",
    instructions=package_analysis_instructions,
    tools=[package_analysis_tool],
    input_guardrails=[basic_guardrail],
)

ticketing_agent = Agent[MoovinAgentContext](
    name="Ticketing Agent",
    model="gpt-4o",
    instructions=ticketing_agent_instructions,
    tools=[create_ticket_tool],
    input_guardrails=[basic_guardrail],
)

general_agent = Agent[MoovinAgentContext](
    name="General Agent",
    model="gpt-4o",
    instructions=general_agent_instructions,
    handoffs=[package_analysis_agent, ticketing_agent],
    input_guardrails=[basic_guardrail],
)

# Enable return handoffs
package_analysis_agent.handoffs.append(general_agent)
ticketing_agent.handoffs.append(general_agent)
