import asyncio
from typing import AsyncIterator, Optional
import contextlib
from agents.realtime import RealtimeAgent, RealtimeRunner
from dotenv import load_dotenv
load_dotenv()
import audioop 
import base64, struct
from array import array
from os import getenv
import audioop
from openai.types.realtime.realtime_audio_formats import AudioPCM

def _extract_pcm_and_rate(audio_obj):
    if audio_obj is None:
        return None, None
    pcm = getattr(audio_obj, "pcm", None)
    if pcm is None:
        pcm = getattr(audio_obj, "pcm16", None)
    if pcm is None:
        pcm = getattr(audio_obj, "bytes", None)
    if pcm is None:
        pcm = getattr(audio_obj, "data", None)
    if isinstance(pcm, memoryview):
        pcm = pcm.tobytes()

    rate = getattr(audio_obj, "sample_rate_hz", None)
    if rate is None:
        rate = getattr(audio_obj, "sample_rate", None)
    if rate is None:
        rate = getattr(audio_obj, "rate", None) 

    if rate is None:
        fmt = getattr(audio_obj, "format", None)
        if fmt is not None:
            rate = (
                getattr(fmt, "sample_rate_hz", None)
                or getattr(fmt, "sample_rate", None)
                or getattr(fmt, "rate", None) 
            )
    if rate is None:
        rate = int(getenv("AGENT_OUT_RATE_DEFAULT", "24000"))
        print(f"[Debug] No se encontró sample_rate en audio obj -> usando {rate} Hz por defecto")
    return pcm, int(rate)



def _to_pcm16_bytes(x):
        """
        Devuelve bytes PCM16 (mono) a 16 kHz cuando sea posible.
        Acepta: bytes/bytearray/memoryview, array('h'), list[int] 16-bit, dicts con {pcm16|bytes|buffer|data},
        o strings base64.
        """
        if x is None:
            return None
        if isinstance(x, (bytes, bytearray, memoryview)):
            return bytes(x)
        if isinstance(x, array) and x.typecode == 'h':
            return x.tobytes()
        if isinstance(x, list) and x and isinstance(x[0], int):
            return struct.pack("<" + "h"*len(x), *x)
        if isinstance(x, dict):
            for k in ("pcm16", "bytes", "buffer", "data", "audio"):
                v = x.get(k)
                b = _to_pcm16_bytes(v)
                if b:
                    return b
            for k in ("b64", "base64"):
                v = x.get(k)
                if isinstance(v, str):
                    try:
                        return base64.b64decode(v)
                    except Exception:
                        pass
            return None
        if isinstance(x, str):
            try:
                return base64.b64decode(x)
            except Exception:
                return None
        tobytes = getattr(x, "tobytes", None)
        if callable(tobytes):
            try:
                return tobytes()
            except Exception:
                return None
        return None
    
def _force_to_8k_pcm16(pcm: bytes, assumed_in_rate: int = 16000, state=None):
    """
    Recibe PCM16 mono (bytes) a cualquier rate (por defecto 16k) y devuelve (pcm8k, new_state).
    """
    if not pcm:
        return b"", state
    if len(pcm) & 1:
        pcm = pcm[:-1]
    try:
        out, state = audioop.ratecv(pcm, 2, 1, assumed_in_rate, 8000, state)
        return out, state
    except Exception:
        return pcm, state
    
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
        await self._session.__aenter__()
        self._pump_task = asyncio.create_task(self._pump_events_to_queue())
        async def _debug_probe_tts():
            text = "Conectado a Silver. Prueba de audio."
            # Intenta nombres comunes en runners/sesiones:
            for m in ("speak", "say", "tts", "respond", "response_create", "start_response"):
                fn = getattr(self._session, m, None)
                if callable(fn):
                    try:
                        res = fn(text)
                        if asyncio.iscoroutine(res):
                            await res
                        print("[Voice] DEBUG: Se invocó", m, "para emitir TTS inicial.")
                        return
                    except Exception as e:
                        print("[Voice] DEBUG:", m, "falló:", repr(e))
            outq = getattr(self._session, "text_out", None)
            if outq:
                try:
                    await outq.put(text)
                    print("[Voice] DEBUG: texto de prueba en 'text_out'")
                except Exception as e:
                    print("[Voice] DEBUG: text_out put falló:", repr(e))
        asyncio.create_task(_debug_probe_tts())

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
        self._bytes_in = getattr(self, "_bytes_in", 0) + len(pcm16_bytes)
        self._last_log_in = getattr(self, "_last_log_in", None)
        import time
        now = time.monotonic()
        if self._last_log_in is None:
            self._last_log_in = now
        if now - self._last_log_in >= 1.0:
            print(f"[Voice] IN agente ~{self._bytes_in} bytes último ~1s")
            self._bytes_in = 0
            self._last_log_in = now
        try:
            converted, self._rate_state_in = audioop.ratecv(
                pcm16_bytes, 2, 1, 8000, 24000, getattr(self, "_rate_state_in", None)
            )
        except Exception:
            converted = pcm16_bytes  # fallback: envía raw si algo falla

        for name in ("send_audio", "send_pcm16", "feed_pcm16", "feed_audio"):
            fn = getattr(self._session, name, None)
            if callable(fn):
                res = fn(converted)   # <-- enviar 16k al agente
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return
        q = getattr(self._session, "audio_in", None)
        if q is not None:
            asyncio.create_task(q.put(converted))  # <-- 16k
            return
        print("WARN: No input audio API found on session")

    async def stream_agent_tts(self):
        """
        Devuelve chunks PCM16 mono listos para enviar al bridge.
        Lee ÚNICAMENTE de la cola _audio_out_q, que es llenada por _pump_events_to_queue().
        """
        while not self._closed:
            pcm = await self._audio_out_q.get()
            if pcm:
                yield pcm

    async def _pump_events_to_queue(self):
        """
        Itera eventos del Realtime y publica PCM en _audio_out_q.
        1) Si hay un stream/cola nativa -> úsala.
        2) Si no, consume eventos y extrae audio; normaliza siempre a 8000 Hz.
        """
        # 1) Streams nativos del runner/sesión
        for mname in ("stream_tts", "audio_stream", "stream_agent_tts", "audio_out_stream"):
            maybe = getattr(self._session, mname, None)
            if callable(maybe):
                print(f"[Voice] DEBUG: usando stream '{mname}'")
                stream = maybe()
                if asyncio.iscoroutine(stream):
                    stream = await stream
                rate_state = None
                async for pcm in stream:
                    b = _to_pcm16_bytes(pcm)
                    if not b:
                        continue
                    b8, rate_state = _force_to_8k_pcm16(b, assumed_in_rate=16000, state=rate_state)
                    if b8:
                        await self._audio_out_q.put(b8)
                return
        for qname in ("audio_out", "pcm16_out", "tts_out"):
            q = getattr(self._session, qname, None)
            if q is not None:
                print(f"[Voice] DEBUG: leyendo de cola '{qname}'")
                rate_state = None
                while not self._closed:
                    pcm = await q.get()
                    b = _to_pcm16_bytes(pcm)
                    if not b:
                        continue
                    b8, rate_state = _force_to_8k_pcm16(b, assumed_in_rate=16000, state=rate_state)
                    if b8:
                        await self._audio_out_q.put(b8)
                return
        print("[Voice] DEBUG: no hay stream/cola directa; iterando eventos de sesión…")
        ratecv_state = None
        async for ev in self._session:
            et = getattr(ev, "type", None)
            if et:
                print("[Voice] DEBUG ev.type:", et)

            if et == "audio":
                audio_obj = getattr(ev, "audio", ev)
                pcm = getattr(audio_obj, "pcm16", None) or getattr(audio_obj, "data", None)
                if not pcm:
                    continue
                # Convertir 24 kHz (SDK) -> 8 kHz (Asterisk)
                self._rate_state_out = getattr(self, "_rate_state_out", None)
                pcm8k, self._rate_state_out = audioop.ratecv(pcm, 2, 1, 24000, 8000, self._rate_state_out)

                if pcm8k:
                    await self._audio_out_q.put(pcm8k)

            elif et == "audio_end":
                pass

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
                "Inicia siempre saludando, presentadote por tu nombre y preguntando cómo puedes ayudar. "
                "Respeta turnos: no pises al usuario. "
                "Si la petición es compleja, Dile siendo picaro y sarcastico, que vienes naciendo, que hace poco aprendiste a hablar y actualmente estas llevando el Training para aprenderlo todo de Moovin!."
            ),
        )

        self._runner = RealtimeRunner(
            starting_agent=voice_agent,
            config={
                "model_settings": {
                "model_name": "gpt-realtime",
                "voice": "alloy",
                "modalities": ["audio"],
                "input_audio_format": AudioPCM(type="audio/pcm", rate=24000),
                "output_audio_format": AudioPCM(type="audio/pcm", rate=24000),
                "input_audio_transcription": {"model": "gpt-4o-mini-transcribe"},
                "noise_reduction": {"type": "far_field"},
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": True,
                    "interrupt_response": False,
                    "eagerness": "low",
                    "silence_duration_ms": 700,
                    "prefix_padding_ms": 250,
                    "idle_timeout_ms": 2500,
                    "threshold": 0.6
                }
            }
            },
        )

        inner_session = await self._runner.run()
        print("[Voice] Realtime conectado (runner listo)")
        return SilverAIVoiceSession(inner_session)
