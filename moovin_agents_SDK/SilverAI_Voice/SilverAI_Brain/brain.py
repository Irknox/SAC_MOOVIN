from agents import (
    Agent,
    handoff,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
)
from agents.agent import ToolsToFinalOutputResult
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from pydantic import BaseModel, Field
from typing import List, Any, Literal, Dict


class AgentInputItem(BaseModel):
    """Representa un ítem en la lista de entradas del agente (historial de chat, tool output, etc.)."""
    role: Literal["user", "assistant", "system", "function"]
    content: str | List[Dict[str, Any]] = Field(default="")
    name: str | None = None
    
BrainInputList = List[AgentInputItem]


class ToolOutputResult(BaseModel):
    """Representa el resultado de la lógica de tool_use_behavior o la salida del BrainRunner."""
    is_final_output: bool
    final_output: str | Dict[str, Any] | None
    
    
class BrainContext(BaseModel):
    session_id: str
    call_id: str
    
class BrainRunner(Runner):
    def __init__(self, packages_tools: List[Any]):
        
        packages_brain: Agent[BrainContext] = Agent[BrainContext](
            name="packages_brain",
            instructions=(
                "Rol:  Eres un 'cerebro' especializado en paquetes, rastreos y envios para una compania de envios y logistica llamada Moovin."
                "Tarea:"
                "Recibir una consulta de un Agente de servicio al cliente y resolverla de la mejor manera basado en tus herramienta, informacion disponible y capacidades."
                "Herramientas disponibles:"
                "- `get_package_timeline`"
                "   - Esta herramienta obtiene los estados de un paquete en orden cronológico, la tienda donde fue comprada, el numero de telefono, nombre del dueño del paquete."
                "   - Número de seguimiento y número de teléfono son los parámetros necesarios."
                "   - Esta herramienta te da los estados del paquete del usuario en orden cronológico, de más reciente a más antiguo, siendo el primero el estado actual del paquete, úsalo para generar un pequeño resumen explicando al usuario que paso con su paquete."
                "   - Tu resumen debe explicar lo sucedido con el paquete hasta el momento actual (Primer estado), los estados siguientes son estados pasados que ya no están activos y de ser incluidos deben ser en tiempo verbal pasado, ya que no están activos, es OBLIGATORIO seguir esta regla, ya que genera inconsistencias y lleva al usuario a pensar que el paquete está en más de un estado cuando no es posible."
                "   - En caso de algún estado importante, por ejemplo: Cancelado, Entregado, Devuelto... Incluye la fecha del estado."
                "   - Nunca omitas información crítica como el estado de entrega ('DELIVERED') sí aparece en el resultado "
                "   - Usa el resultado de esta herramienta para generar un pequeño resumen al usuario, siendo breve e incluyendo sólo los estados con el símbolo "+" en la lista de estados."
                "   - Si mencionas que un paquete salió del país, informa que es el país de origen (Lo que quiere decir que viene en dirección a Costa Rica) ya que puede darse a malinterpretaciones"
                "   - La respuesta al usuario debe ser un resumen **coherente y narrativo**, que explique el proceso del paquete hasta el momento actual."
                "   - **Nunca** generes una lista (numerada o con viñetas) en la respuesta al usuario, ni describas los estados uno por uno ni en secuencia aislada."
                "   - Si el nombre de la tienda donde fue comprado esta disponible, es *OBLIGATORIO* que lo uses, si no está disponible, NO le menciones al usuario ningún detalle sobre la tienda."
                "   - Debe ser una explicación fluida, clara, humana y sin contradicciones temporales. Por ejemplo, no puedes decir que está 'en nuestras instalaciones' y luego que está 'ya entregado', ya que el paquete no puede estar en más de 1 estado a la vez."
                "   - Si el usuario solicita las fechas proporcionalas al usuario."
            ),
            tools=packages_tools,
        )
        
        routing_brain: Agent[BrainContext] = Agent[BrainContext](
            name="routing_brain",
            instructions=(
                RECOMMENDED_PROMPT_PREFIX +
                "Eres el 'Routing Brain' dentro de la red neuronal de Moovin Agents, un sistema distribuido de agentes especializados. Tu única función es analizar cada consulta recibida desde un Agente de Servicio al Cliente y determinar a qué cerebro especializado (brain) debe redirigirse dicha consulta y realizar un handoff al cerebro correcto."
                "Actualmente, los cerebros especializados disponibles son:"
                "- packages_brain: Maneja consultas relacionadas con paquetes, envíos, entregas, seguimiento, logística, o problemas similares."
                "Si la consulta no está relacionada con paquetes o no puedes determinar con certeza qué cerebro debería encargarse, responde con: "
                "No puedo procesar esta consulta en este momento."
                "No intentes resolver la consulta ni dar una respuesta por tu cuenta. Tu única función es enrutar correctamente."
            ),
            tools=[],
            handoffs=[packages_brain]

        )

        self.agent: Agent[BrainContext] = routing_brain
        
    async def execute_query(self, input_items: BrainInputList, context: BrainContext) -> ToolOutputResult:
            """
            Ejecuta el flujo multi-agente Standard (los 'cerebros') 
            a partir del nodo inicial definido (routing_brain).
            """
            wrapper = RunContextWrapper(self.agent, context)
            sdk_result = await wrapper.run(input_items)
            final_output = getattr(sdk_result, 'final_output', None)
            is_final = bool(final_output)
            return ToolOutputResult(
                is_final_output=is_final,
                final_output=final_output
            )