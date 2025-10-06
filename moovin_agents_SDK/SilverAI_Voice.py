import asyncio
from typing import AsyncIterator, Optional
import contextlib
from agents.realtime import RealtimeAgent, RealtimeRunner


class SilverAIVoiceSession:
    """
    Envoltura sobre la sesión del SDK Realtime para exponer:
      - feed_pcm16(bytes)  -> push de audio entrante (caller -> agente)
      - stream_agent_tts() -> iteración de audio saliente (agente -> caller)

    También actúa como context manager asíncrono.
    """
    def __init__(self, inner_session):
        self._session = inner_session
        self._audio_out_q: asyncio.Queue[bytes] = asyncio.Queue()
        self._pump_task: Optional[asyncio.Task] = None
        self._closed = False

    async def __aenter__(self):
        # Arranca un “pump” que escucha eventos de la sesión real y
        # encola los chunks de audio PCM16 salientes en _audio_out_q.
        await self._session.__aenter__()         
        await self._pump_task == asyncio.create_task( 
                self._pump_events_to_queue()
            )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._closed = True
        if self._pump_task:
            self._pump_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pump_task
        await self._session.__aexit__(exc_type, exc, tb)

    def feed_pcm16(self, pcm16_bytes: bytes) -> None:
        """
        Empuja audio entrante (PCM16 mono 16-bit, 8 kHz) al agente.
        Intentamos métodos comunes del runner para no acoplar al detalle.
        """
        #
        for name in ("send_audio", "send_pcm16", "feed_pcm16", "feed_audio"):
            fn = getattr(self._session, name, None)
            if callable(fn):
                res = fn(pcm16_bytes)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return
        q = getattr(self._session, "audio_in", None)
        if q is not None:
            asyncio.create_task(q.put(pcm16_bytes))
            return

        # Si llegamos aquí, no hay API conocida.
        print("WARN: No input audio API found on session")
        return

    async def stream_agent_tts(self) -> AsyncIterator[bytes]:
        """Itera chunks PCM16 salientes del agente (para enviarlos a Asterisk)."""
        while not self._closed:
            chunk = await self._audio_out_q.get()
            if chunk:
                yield chunk

    # ====== Internals ======
    async def _pump_events_to_queue(self):
        """
        Lee eventos de la sesión Realtime y publica audio PCM16 en _audio_out_q.
        """
        #
        for mname in ("stream_tts", "audio_stream", "stream_agent_tts"):
            maybe = getattr(self._session, mname, None)
            if callable(maybe):
                stream = maybe()
                if asyncio.iscoroutine(stream):
                    stream = await stream
                async for pcm in stream:
                    if pcm:
                        await self._audio_out_q.put(pcm)
                return  # si el stream acaba, se deja de anadir eventos

        async for ev in self._session:
            if getattr(ev, "type", "") == "audio":
                for attr in ("pcm16", "samples", "data", "buffer", "bytes"):
                    pcm = getattr(ev, attr, None)
                    if pcm:
                        await self._audio_out_q.put(pcm)
                        break


class SilverAIVoice:
    """
    Orquesta la creación del agente y devuelve SilverAIVoiceSession,
    que es lo que tu ARI debe usar.
    """
    def __init__(self):
        self._runner: Optional[RealtimeRunner] = None

    async def start(self) -> SilverAIVoiceSession:
        voice_agent = RealtimeAgent(
            name="Silver AI Voice Agent",
            instructions=(
                "Eres un agente de VOZ para Moovin. Tu nombre es Silver. "
                "Respeta turnos: no pises al usuario. "
                "Si la petición es compleja, ofrece seguir por pasos."
            ),
        )

        self._runner = RealtimeRunner(
            starting_agent=voice_agent,
            config={
                "model_settings": {
                    "model_name": "gpt-realtime",
                    "voice": "alloy",
                    "modalities": ["audio"],
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "gpt-4o-mini-transcribe"},
                    "turn_detection": {
                        "type": "semantic_vad",
                        "interrupt_response": True
                    },
                }
            },
        )

        inner_session = await self._runner.run()
        return SilverAIVoiceSession(inner_session)
