import os, asyncio
from dotenv import load_dotenv
from main import build_agents 
from agents.realtime import RealtimeAgent, RealtimeRunner
from api import _load_initial_prompts  
from config import create_mysql_pool, create_tools_pool  

load_dotenv()

async def main():
    mysql_pool = await create_mysql_pool()
    tools_pool = await create_tools_pool()
    prompts = _load_initial_prompts()

    general, package, mcp, railing, create_initial_context = await build_agents(
        tools_pool, mysql_pool, prompts
    )

    voice_agent = RealtimeAgent(
        name="Voice Agent",
        instructions="\n\n".join([
            "Eres un agente de VOZ para Moovin. Escucha, responde breve si es trivial y "
            "si la consulta requiere análisis/acción, deriva por handoff al agente correcto. "
            "Habla en español y en tono claro.",
            prompts["General Prompt"].strip(),  
        ]),
        handoffs=[general, package, mcp, railing],
    )

    runner = RealtimeRunner(
        starting_agent=voice_agent,
        config={
            "model_settings": {
                "model_name": "gpt-realtime",
                "voice": "alloy",                 
                "modalities": ["audio"],          
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {"model": "gpt-4o-mini-transcribe"},
                "turn_detection": {"type": "semantic_vad", "interrupt_response": True},
            }
        },
    )

    session = await runner.run()

    async with session:
        print("✅ Sesión de voz activa. El agente hablará en tiempo real.")
        async for event in session:
            if event.type == "handoff":
                print(f"🔀 Handoff: {event.from_agent.name} → {event.to_agent.name}")
            elif event.type == "tool_start":
                print(f"🛠️ Tool start: {event.tool.name}")
            elif event.type == "tool_end":
                print(f"🛠️ Tool end: {event.tool.name}; output: {event.output}")
            elif event.type == "audio":
                pass
            elif event.type == "audio_interrupted":
                print("⏸️ Audio interrumpido (barge-in)")
            elif event.type == "error":
                print(f"⚠️ Error: {event.error}")

if __name__ == "__main__":
    asyncio.run(main())
