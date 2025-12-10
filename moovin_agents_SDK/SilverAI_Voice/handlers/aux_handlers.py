import os
import json
import asyncio
from openai import AsyncOpenAI 

client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

async def resume_interaction(interactions: list) -> str:
    """
    Función que toma las interacciones cliente-agente, las pasa a un LLM que se 
    encarga de resumir la conversación antes de persistir los datos y cerrar la sesión.
    
    Args:
        interactions (list): Lista de objetos de interacción (turnos) recuperados de Redis.
        
    Returns:
        str: El resumen generado por el LLM, o un mensaje de error si falla.
    """
    
    transcript_lines = []
    
    for interaction in interactions:
        if interaction.get("user") and interaction["user"].get("text"):
            transcript_lines.append(f"USUARIO: {interaction['user']['text']}")
        
        if interaction.get("agent") and interaction["agent"].get("text"):
            transcript_lines.append(f"AGENTE: {interaction['agent']['text']}")
            
    full_transcript = "\n".join(transcript_lines)
    
    
    system_prompt = (
        "Eres un experto en resumir interacciones de un Agente de Soporte al Cliente y el usuario para una compañia de envios y logistica. "
        "Tu tarea es generar un resumen apartir de la transcripción completa de la conversación. "
        "Incluye el motivo de la llamada, las acciones tomadas y todo detalle de importancia en la interacción."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Por favor, resume la siguiente conversación:\n\n---\n\n{full_transcript}"}
    ]
    
    try:
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0,
        )
        
        summary = completion.choices[0].message.content.strip()
        print(f"[DEBUG] Resumen generado exitosamente: {summary}")
        return summary
        
    except Exception as e:
        error_message = f"Error al generar resumen con LLM: {str(e)}"
        print(f"[ERROR] {error_message}")
        return f"ERROR: Fallo la generación del resumen. Detalle: {str(e)}"
