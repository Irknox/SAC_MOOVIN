# api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any,Literal
from uuid import uuid4
import time

class AgentEvent(BaseModel):
    id: str
    type: Literal["handoff", "tool_call", "tool_output"]
    agent: str
    content: str

class MessageResponse(BaseModel):
    content: str
    agent: str

class GuardrailCheck(BaseModel):
    name: str = "Unnamed"
    passed: bool = True
    message: str = ""

from main import (
    general_agent,
    package_analysis_agent,
    ticketing_agent,
    create_initial_context
)

from agents import (
    Runner,
    MessageOutputItem,
    HandoffOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    InputGuardrailTripwireTriggered,
    Handoff,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str

class ChatResponse(BaseModel):
    conversation_id: str
    current_agent: str
    messages: List[MessageResponse]
    events: List[AgentEvent]
    context: Dict[str, Any]
    agents: List[Dict[str, Any]]
    guardrails: List[GuardrailCheck] = []

class InMemoryStore:
    _store: Dict[str, Dict[str, Any]] = {}

    def get(self, cid: str) -> Optional[Dict[str, Any]]:
        return self._store.get(cid)

    def save(self, cid: str, state: Dict[str, Any]):
        self._store[cid] = state

store = InMemoryStore()

def _get_agent_by_name(name: str):
    agents = {
        general_agent.name: general_agent,
        package_analysis_agent.name: package_analysis_agent,
        ticketing_agent.name: ticketing_agent,
    }
    return agents.get(name, general_agent)

def _list_agents():
    def agent_dict(agent):
        return {
            "name": agent.name,
            "description": getattr(agent, "handoff_description", ""),
            "tools": [t.name for t in getattr(agent, "tools", [])],
            "handoffs": [h.agent_name for h in getattr(agent, "handoffs", [])],
        }
    return [agent_dict(a) for a in [general_agent, package_analysis_agent, ticketing_agent]]

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    is_new = not req.conversation_id or store.get(req.conversation_id) is None

    if is_new:
        cid = uuid4().hex
        ctx = create_initial_context()
        state = {
            "context": ctx,
            "input_items": [],
            "current_agent": general_agent.name,
        }
        store.save(cid, state)
    else:
        cid = req.conversation_id
        state = store.get(cid)

    current_agent = _get_agent_by_name(state["current_agent"])
    state["input_items"].append({"role": "user", "content": req.message})

    try:
        result = await Runner.run(current_agent, state["input_items"], context=state["context"])
    except InputGuardrailTripwireTriggered as e:
        return ChatResponse(
            conversation_id=cid,
            current_agent=current_agent.name,
            messages=[MessageResponse(content="Guardrail activated. Input rejected.", agent=current_agent.name)],
            events=[],
            context=state["context"].model_dump(),
            agents=_list_agents(),
            guardrails=[],
        )

    messages, events = [], []
    for item in result.new_items:
        if isinstance(item, MessageOutputItem):
            msg = item.output.content if hasattr(item.output, "content") else str(item.output)
            messages.append(MessageResponse(content=msg, agent=item.agent.name))
        elif isinstance(item, HandoffOutputItem):
            events.append(AgentEvent(
                id=uuid4().hex,
                type="handoff",
                agent=item.source_agent.name,
                content=f"{item.source_agent.name} -> {item.target_agent.name}",
            ))
            current_agent = item.target_agent
        elif isinstance(item, ToolCallItem):
            events.append(AgentEvent(
                id=uuid4().hex,
                type="tool_call",
                agent=item.agent.name,
                content=str(item.raw_item.name)
            ))
        elif isinstance(item, ToolCallOutputItem):
            events.append(AgentEvent(
                id=uuid4().hex,
                type="tool_output",
                agent=item.agent.name,
                content=str(item.output)
            ))

    state["input_items"] = result.to_input_list()
    state["current_agent"] = current_agent.name
    store.save(cid, state)

    return ChatResponse(
        conversation_id=cid,
        current_agent=current_agent.name,
        messages=messages,
        events=events,
        context=state["context"].model_dump(),
        agents=_list_agents(),
        guardrails=[],
    )
