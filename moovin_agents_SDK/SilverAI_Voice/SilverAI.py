from flask import Flask, request, Response
from openai import OpenAI, InvalidWebhookSignatureError
import asyncio
import json
import os
import threading
from agents import (Agent, input_guardrail, output_guardrail, RunContextWrapper, Runner,GuardrailFunctionOutput)
from agents.realtime import RealtimeAgent, RealtimeRunner
from agents.realtime.openai_realtime import OpenAIRealtimeSIPModel
from websockets.exceptions import ConnectionClosedError
import requests
from requests import HTTPError
from tools import escalate_call,Make_think_tool
from datetime import datetime
from handlers.aux_handlers import resume_interaction
from handlers.db_handlers import (
    save_to_mongodb, 
    save_call_meta, 
    interaction_key, 
    append_interaction, 
    redis_key, 
    get_session_data, 
    delete_session_data,
    create_mysql_pool,
    create_tools_pool,
)
from pydantic import BaseModel
import pymongo
from SilverAI_Brain.brain import BrainRunner
from SilverAI_Brain.tools import Make_get_package_timeline_tool,Make_request_to_pickup_tool,Make_request_electronic_receipt_tool,Make_package_damaged_tool
from typing import Optional, Dict, Any, List

MONGO_URI = os.environ.get("MONGO_URI") 
MONGO_DATABASE = os.environ.get("MONGO_DATABASE") 
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION")

GENERAL_PROMPT = 'General_prompt.txt'
base_dir = os.path.dirname(os.path.abspath(__file__))
PROMPT_FILE_PATH = os.path.join(base_dir, 'prompts', GENERAL_PROMPT)

try:
    with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
        prompt_text = f.read()
        print(f"[INFO] Instrucciones cargadas exitosamente desde: {PROMPT_FILE_PATH}")
        
except FileNotFoundError:
    prompt_text = "Eres un Agente de Servicio al Cliente para la compañía de logística y envíos Moovin (pronunciado 'Muvin'). Respondes con voz natural, en español latino, de forma clara y concisa." 
    print(f"[ERROR] No se pudo encontrar el archivo de instrucciones en: {PROMPT_FILE_PATH}. Usando instrucciones por defecto.")
    
try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_client.admin.command('ping') 
    db = mongo_client[MONGO_DATABASE]
    sessions_collection = db[MONGO_COLLECTION]
    print(f"[INFO] Conexión a MongoDB exitosa. URI: {MONGO_URI}, Colección: {MONGO_COLLECTION}")
except Exception as e:
    print(f"[ERROR] No se pudo conectar a MongoDB. La persistencia fallará: {e}")
    mongo_client = None
    sessions_collection = None
    
app = Flask(__name__)

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    webhook_secret=os.environ["OPENAI_WEBHOOK_KEY"],
)     
    
AUTH_HEADER = {
    "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY"),
}

call_accept = {
    "type": "realtime",
    "instructions": (
        "Eres un Agente de Servicio al Cliente para la compañía de logística y envíos Moovin "
        "(pronunciado 'Muvin')."
        "Habla en español latino, manten un tono natural, sin acentos."
    ),
    "model": "gpt-4o-realtime-preview",
}


async def run_realtime_session(call_id: str):
    """Engancha un RealtimeAgent (SDK) a la llamada SIP usando el call_id
    que llega por el webhook realtime.call.incoming.
    """  
    print(f"[{call_id}] 👂 Iniciando sesión de Realtime...")
    Tools_pool = await create_tools_pool()
    
    
    #Guardarailes
    class GuardrailContext(BaseModel):
        passed: bool | None = None
        reason: str | None = None
        input_received: str | None = None
        
    class GuardrailOutput(BaseModel):
        reasoning: str
        passed: bool
        
    output_guardrail_agent=Agent[GuardrailContext](
        name="Output Guardrail Agent",
        model="gpt-4o-mini",
        instructions=(
            "Funcionas como un guardrail que filtra las respuesta de un Agente de Servicio al cliente para la compañia Moovin(Pronunciada Muuvin)."
            "Tarea: Analizala respuesta del agente y determina si esta fuera del contexto permitido para la atencion o es invalido. Para poder determinar esto recibes contexto sobre Moovin y las capacidades del asistente virtual."
            
            "Ejemplo de temas sobre los que el agente NO debe interactuar:"
                "   -Teorias de conspiracion."
                "   -Politica."
                "   -Religión."
                "   -Otras compañias."
                "   -Consultas relacionadas al funcionamiento del asistente virtual."
                "   -Cualquer otro tema que NO este directamente relacionados a Moovin o su servicio de envios y logistica."
                
            "Ejemplo de contexto sobre Moovin:"
            "   - Moovin es una empresa de logística costarricense, también presente en Honduras y Chile, especializada en entregas rápidas y seguras. Si recibes una notificación nuestra, es porque estamos encargados de llevarte un pedido que hiciste en otra tienda (nacional o internacional). "
            "   - Servicios principales:"
            "   - Recolección y entrega de paquetes en ruta."
            "   - Entrega local de paquetes internacionales."
            "   - Entregas al mismo día (Envíos Exprés)."
            "   - Almacenaje de productos (Fulfillment)."
            "   - Venta de bolsas y empaques. (Ticket MCP Agent)"
            "   - Cobro contra entrega de productos (Cash on delivery)."

            "Notas:"
            "  -Tu tarea es UNICAMENTE validar la respuesta del agente, no debes validar si realizo el proceso correcto o si la atencion fue correcta."
            "  -Si la respuesta del agente contiene contenido fuera del contexto permitido, debes marcarla como inválida."
            
            "Respondes con unn json que contiene los siguientes campos:"
            "   - reasoning: Explica brevemente por qué la respuesta es válida o inválida."
            "   - passed: Booleano que indica si la respuesta es válida (true) o inválida (false)."
        ),
        output_type=GuardrailOutput, 
    )
    
    @output_guardrail(name="Output Guardrail Function")
    async def silver_output_guardrail(
        context: RunContextWrapper[GuardrailContext], 
        agent: Agent, 
        output: str
    ) -> GuardrailFunctionOutput:
        print(f"[DEBUG-GUARDRAIL] Evaluando respuesta del agente: '{output[:50]}...'")
        result = await Runner.run(output_guardrail_agent, output, context=context.context)
        final = result.final_output_as(GuardrailOutput)
        print(f"[GUARDRAIL] Resultado para '{output[:30]}': {final.passed} - Razón: {final.reasoning}")
        if not final.passed:
            print(f"[GUARDRAIL] 🚩 BLOQUEADO: {final.reasoning}")
            session = context.context.get("realtime_session")
            if session:
                rescue_agent = create_railing_agent(final.reasoning, output)
                await session.update_agent(rescue_agent)
            
            return GuardrailFunctionOutput(
                output_info=final,
                tripwire_triggered=True, 
            )

        return GuardrailFunctionOutput(output_info=final, tripwire_triggered=False)
    #Iniciacion de tools con pools para el brain runner
    
    #Tools para paqueteria
    packages_tools = [ Make_get_package_timeline_tool(Tools_pool)]
    
    #Tools para ticketing
    ticketing_tools = [
    Make_request_to_pickup_tool(Tools_pool),
    Make_request_electronic_receipt_tool(Tools_pool),
    Make_package_damaged_tool(Tools_pool),
    ]
    brain_runner = BrainRunner(packages_tools,ticketing_tools)
    
    ## Inicializacion de agente de voz
    think_tool = Make_think_tool(call_id, brain_runner)

    voice_agent = RealtimeAgent(
        name="Silver",
        instructions=prompt_text,
        tools=[escalate_call, think_tool],  
        output_guardrails=[silver_output_guardrail] 
    )

    def create_railing_agent(reason: str, input_received: str) -> RealtimeAgent:      
        railing_agent = RealtimeAgent(
                name="Railing Agent",
                instructions=(
                    "Eres un agente encargado en reorientar la conversacion cuando esta se salga del contexto de servicio al cliente para la compañia de envios y logistica Moovin.(pronunciada Muvin)"
                    "Tarea: Recibes la razon por la que el guadarail fue activado y el input que provoco la activacion."
                    f"   Razon de activacion del guardrail: {reason}"
                    f"   Input que provoco la activacion: {input_received}"
                    "   - A partir de esto reformulas la respuesta del agente a algo valido o reorientas al usuario hacia un tema relacionado con el servicio al cliente de Moovin."
                    "   - Ten en cuenta que el guardarail puede ser activado por el mensaje del usuario o respuesta del agente."
                    "Contexto invalido para consultas:"
                    "   -Teorias de conspiracion."
                    "   -Politica."
                    "   -Religión."
                    "   -Otras compañias."
                    "   -Consultas relacionadas al funcionamiento del asistente virtual."
                    "   -Cualquer otro tema que NO este directamente relacionados a Moovin o su servicio de envios y logistica."

                    "Contexto sobre Moovin(Valido para consultas):"
                    "   - Moovin es una empresa de logística costarricense, también presente en Honduras y Chile, especializada en entregas rápidas y seguras. Si recibes una notificación nuestra, es porque estamos encargados de llevarte un pedido que hiciste en otra tienda (nacional o internacional). "
                    "   - Servicios principales:"
                    "   - Recolección y entrega de paquetes en ruta."
                    "   - Entrega local de paquetes internacionales."
                    "   - Entregas al mismo día (Envíos Exprés)."
                    "   - Almacenaje de productos (Fulfillment)."
                    "   - Venta de bolsas y empaques. (Ticket MCP Agent)"
                    "   - Cobro contra entrega de productos (Cash on delivery)."
                    
                    "Como funciona Moovin?"
                    "   - Haces tu compra en linea en una tienda nacional o internacional, y estas tiendas nos contactan para entregarte el pedido. En la modalidad contratada."
                    "   - Los repartidores se llaman Moovers."
                    "   - Colaboramos con e-commerce nacionales e internacionales para facilitar entregas locales, entre las más comunes, Temu, Aliexpress, Amazon entre otras."
                    "   - Moovin no envia paquetes al extranjero, se puede contratar la recolección y entrega de un paquete a nivel nacional, en caso de entregas de paquetes internacionales, hace referencia a usuarios que compraron artículos fuera del país y la compañía internacional contrata a Moovin para la distribución a nivel nacional o bajo la cobertura contratada."
                    ""
                ),
                tools=[ ],
                handoffs=[voice_agent]    
            )
        return railing_agent
    
    runner = RealtimeRunner(
        starting_agent=voice_agent,
        model=OpenAIRealtimeSIPModel(),
    )
    
    current_interaction = {
        "user": None, 
        "steps_taken": [], 
        "agent": None,
        "date": datetime.now().isoformat(), 
        }
    processed_item_ids = set()
    tool_calls_pending = {}
    
    
    def finalize_and_save_interaction(call_id: str, current_interaction: dict) -> dict:
        """Consolida el current_interaction y lo añade a la lista de Redis, 
           luego prepara el nuevo objeto de interacción.
           Retorna el nuevo objeto de interacción."""
        if current_interaction["user"] or current_interaction["agent"] or current_interaction["steps_taken"]:
            interaction_to_save = current_interaction.copy() 
            append_interaction(call_id, interaction_to_save)
        
        new_interaction = {
            "user": None, 
            "steps_taken": [], 
            "agent": None,
            "date": datetime.now().isoformat(),
        }
        return new_interaction
    
    def extract_text_from_item(item) -> str | None:
        """Extrae el texto relevante (transcript o text) de un RealtimeItem."""
        #print (f"[DEBUG-EXTRACT] Item recibido en Extractor: {item}")
        if getattr(item, 'role', 'system') == "system" or not hasattr(item, 'content') or not item.content:
            return None 
        for content_item in item.content:
            if item.role == "assistant":
                transcript = getattr(content_item, 'transcript', None)
                if transcript:
                    return transcript
            elif item.role == "user":
                transcript = getattr(content_item, 'transcript', None)
                if transcript:
                    return transcript
                
        return None
    
    model_config = {
        "call_id": call_id,
        "initial_model_settings": {
            "modalities": ["audio"],
            "voice": "echo",
            "speed": 1.3,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "gpt-4o-mini-transcribe",
            },
            "input_audio_noise_reduction": {
                "type": "near_field",
            },
            "turn_detection": {
                "type": "server_vad",
                "interrupt_response": True,
                "threshold": 0.8,
            },
        },
    }
    try:
        ctx = {
        "call_id": call_id,
        }
        async with await runner.run(context=ctx,model_config=model_config) as session:
            initial_message = "Hola, soy Silver, asistente virtual de Moovin (pronunciado Muvin), ¿cómo puedo asistirte hoy?"
            ctx["realtime_session"] = session
            await session.send_message(
                f"Dile al usuario: '{initial_message}'"
            )
            current_interaction["agent"] = {
                "text": initial_message,
                "date": datetime.now().isoformat(),
            }
            current_interaction = finalize_and_save_interaction(call_id, current_interaction)
            async for event in session:
                if event.type == "raw_model_event":
                    pass
                elif event.type == "agent_start" or event.type == "agent_end":
                    #print(f"[DEBUG] Evento recibido: {event}")
                    continue
                elif event.type == "audio_start" or event.type == "audio_end":
                    #print(f"[DEBUG] Evento recibido: {event}")
                    continue
                    
                elif event.type == "function.call.created":
                    tool_call_id = event.data.tool_call_id
                    
                    tool_calls_pending[tool_call_id] = {
                        "type": "tool_call",
                        "tool_name": event.data.tool_name,
                        "arguments": event.data.arguments,
                        "date_started": datetime.now().isoformat(),
                    }
                    current_interaction["steps_taken"].append(tool_calls_pending[tool_call_id])
                elif event.type == "history_added":
                    item = getattr(event, 'item', None)
                    if item:
                        #print(f"[DEBUG-HISTORY-ADDED] Item nuevo: {item}")
                        continue
                    continue
                
                elif event.type == "history_updated":
                    if not hasattr(event, 'history') or not event.history:
                        #print(f"[DEBUG-HISTORY-UPDATED] Evento {event.type} recibido con history=[] o sin history.")
                        continue
                    #print(f"[DEBUG-HISTORY-UPDATED] Evento: {event} recibido con history: {event.history}")
                    for item in event.history:
                        if item.item_id in processed_item_ids:
                            continue    
                        if not hasattr(item, 'role'):
                            if item.status == "completed":
                                processed_item_ids.add(item.item_id)
                            continue
                        if item.role == "user" and item.status != "completed":
                            continue
                        text = extract_text_from_item(item)

                        if text:
                            role = item.role
                            #print(f"[DEBUG-EXTRACT-FINAL] Texto extraído FINAL. Rol: {role}, Status: {item.status}, Texto: '{text}'")
                            if role == "user":
                                if current_interaction["agent"]:
                                    current_interaction = finalize_and_save_interaction(call_id, current_interaction)
                                current_interaction["user"] = {
                                    "text": text,
                                    "date": datetime.now().isoformat(),
                                }
                            elif role == "assistant":
                                current_interaction["agent"] = {
                                    "text": text,
                                    "date": datetime.now().isoformat(),
                                }
                                current_interaction = finalize_and_save_interaction(call_id, current_interaction)
                            processed_item_ids.add(item.item_id)
                            #print(f"[DEBUG-TURN-SAVED] Turno finalizado y guardado. Item ID: {item.item_id}, Rol: {role}")                               
                        elif item.status == "completed":
                            processed_item_ids.add(item.item_id)
                           # print(f"[DEBUG-COMPLETED-NO-TEXT] Item completado sin texto relevante (probablemente InputText o tool call). Item ID: {item.item_id}")
                elif event.type == "function.call.completed":
                    tool_call_id = event.data.tool_call_id
                    if tool_call_id in tool_calls_pending:
                        tool_entry = tool_calls_pending[tool_call_id]
                        tool_entry["date_completed"] = datetime.now().isoformat()
                        tool_entry["output"] = event.data.output
                        tool_entry["status"] = "completed"
                        del tool_calls_pending[tool_call_id]
    except ConnectionClosedError as e:
        print(f"[ERROR-NETWORK] Sesión Realtime cerrada abruptamente (WebSocket/RTP) para call_id={call_id}: {type(e).__name__}: {str(e)}")
    except Exception as e:
        print(f"[ERROR-SESSION] Sesión Realtime fallida para call_id={call_id}: {type(e).__name__}: {str(e)}")
        raise e 
    finally:
        current_interaction = finalize_and_save_interaction(call_id, current_interaction) 
        meta_json, interactions_list = get_session_data(call_id)
        interacion_summary = await resume_interaction(interactions_list)
        full_session_data = None
        if meta_json:
            meta = json.loads(meta_json)
            meta["finish_date"] = datetime.now().isoformat()
            session_status = "ended_with_error" if 'e' in locals() else "ended_cleanly"
            meta["status"] = session_status
            meta["summary"] = interacion_summary or "No se pudo generar resumen."
            save_call_meta(call_id, meta) 
            full_session_data = {**meta, "interactions": interactions_list}
            if full_session_data:
                save_to_mongodb(sessions_collection, full_session_data)
        if full_session_data:
            print(f"[DEBUG] Sesión Completa para Persistencia (call_id={call_id}):")
            print(f"  - Status Final: {full_session_data['status']}")
            print(f"  - Total Interacciones: {len(full_session_data['interactions'])}")
            
            if len(full_session_data['interactions']) > 0:
                 print(f"  - Primera Interacción: {json.dumps(full_session_data['interactions'][0])}")
        else:
            print(f"[DEBUG] No se encontró metadata en Redis para call_id={call_id} antes de limpiar.")
        delete_session_data(call_id)
        print(f"[DEBUG] Redis cleanup OK para call_id={call_id}")
          
def start_session_in_thread(call_id: str):
    """
    Wrapper para lanzar la sesión async del SDK en un thread.
    Instancia BrainRunner y lo pasa a la sesión asíncrona.
    """
    asyncio.run(run_realtime_session(call_id))

@app.route("/", methods=["POST"])
def webhook():
    try:
        event = client.webhooks.unwrap(request.data, request.headers)
        
        if event.type == "realtime.call.incoming":
            call_id = event.data.call_id
            sip_headers = {}
            for h in (event.data.sip_headers or []):
                sip_headers[h.name] = h.value
            print(f"Incoming call: {call_id}, SIP headers: {sip_headers}")
            
            session_meta = {
                "session_id": call_id,
                "summary": None,
                "init_date": event.created_at, 
                "finish_date": None,
                "status": "incoming", 
                "user_info": { 
                    "phone_number": sip_headers.get("From", "Unknown"), 
                },
                "meta_data": {         
                    "x_ast_uniqueid": sip_headers.get("X-Ast-UniqueID"),
                    "x_ast_channel": sip_headers.get("X-Ast-Channel"),
                    "sip_call_id": sip_headers.get("Call-ID"),
                    "sip_headers": sip_headers,
                },
            }
            
            save_call_meta(call_id, session_meta) 
            
            requests.post(
                f"https://api.openai.com/v1/realtime/calls/{call_id}/accept",
                headers={**AUTH_HEADER, "Content-Type": "application/json"},
                json=call_accept,
            )

            threading.Thread(
                target=start_session_in_thread,
                args=(call_id,),
                daemon=True,
            ).start()

        return Response(status=200)

    except InvalidWebhookSignatureError as e:
        print("Invalid signature", e)
        return Response("Invalid signature", status=400)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8585)