# SilverAI_Brain/brain.py

from agents import (
    Agent,
    handoff,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
)
from agents.agent import ToolsToFinalOutputResult
from pydantic import BaseModel
from typing import List

class BrainContext(BaseModel):
    session_id: str
    call_id: str
    
class BrainRunner(Runner[BrainContext]):
    routing_node: Agent[BrainContext] = Agent[BrainContext](
        name="routing_node",
        description="Determina la naturaleza de la consulta y enruta a nodos especializados.",
        instructions=(
            "Eres el Agente de Enrutamiento del sistema especializado Moovin. "
            "Tu única tarea es analizar la última consulta y decidir el nodo al que hacer handoff. "
            "Si la consulta es sobre un envío, haz handoff a 'packages_node'. Si no es claro, responde que no puedes contestar eso en este momento"
        ),
        tools=[]
    )

    packages_node: Agent[BrainContext] = Agent[BrainContext](
        name="packages_node",
        description="Maneja consultas relacionadas con el rastreo de paquetes.",
        instructions="Eres el Agente Especializado en Logística Moovin. Usa tus herramientas de API para rastrear. Cuando tengas una respuesta concisa, haz handoff de vuelta al routing_node para terminar la sesión del cerebro.",
        tools=[
        ],
        handoffs=[routing_node] 
    )
    routing_node.handoffs.append(packages_node)
    
    agent: Agent[BrainContext] = routing_node

    async def execute_query(self, input_items: List[TResponseInputItem], context: BrainContext) -> ToolsToFinalOutputResult:
        """
        Ejecuta el flujo multi-agente Standard (los 'cerebros') 
        a partir del nodo inicial definido (routing_node).
        """
        wrapper = RunContextWrapper(self.agent, context)

        return await wrapper.run(input_items)