import asyncio
from typing import AsyncIterator, Optional
import contextlib
from agents.realtime import RealtimeAgent, RealtimeRunner
from dotenv import load_dotenv
load_dotenv()
import audioop 
import base64, struct
from array import array


def _to_pcm16_bytes(x):
        """
        Devuelve bytes PCM16 (mono) a 16 kHz cuando sea posible.
        Acepta: bytes/bytearray/memoryview, array('h'), list[int] 16-bit, dicts con {pcm16|bytes|buffer|data},
        o strings base64.
        """
        if x is None:
            return None
        # bytes-like directos
        if isinstance(x, (bytes, bytearray, memoryview)):
            return bytes(x)
        # array de 16-bit (signed)
        if isinstance(x, array) and x.typecode == 'h':
            return x.tobytes()
        # lista de enteros 16-bit
        if isinstance(x, list) and x and isinstance(x[0], int):
            return struct.pack("<" + "h"*len(x), *x)
        # dict con posibles contenedores
        if isinstance(x, dict):
            for k in ("pcm16", "bytes", "buffer", "data", "audio"):
                v = x.get(k)
                b = _to_pcm16_bytes(v)
                if b:
                    return b
            # a veces { "b64": "..."} o similar
            for k in ("b64", "base64"):
                v = x.get(k)
                if isinstance(v, str):
                    try:
                        return base64.b64decode(v)
                    except Exception:
                        pass
            return None
        # string como base64
        if isinstance(x, str):
            try:
                return base64.b64decode(x)
            except Exception:
                return None
        # objeto con tobytes()
        tobytes = getattr(x, "tobytes", None)
        if callable(tobytes):
            try:
                return tobytes()
            except Exception:
                return None
        return None
    
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
                pcm16_bytes,  # data
                2,            # width=2 bytes (16-bit)
                1,            # nchannels=1 (mono)
                8000,         # inrate
                16000,        # outrate
                getattr(self, "_rate_state_in", None)
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

    async def stream_agent_tts(self) -> AsyncIterator[bytes]:
        """Itera chunks PCM16 salientes del agente (para enviarlos a Asterisk)."""
        while not self._closed:
            chunk = await self._audio_out_q.get()
            if chunk:
                self._bytes_out = getattr(self, "_bytes_out", 0) + len(chunk)
                self._last_log_out = getattr(self, "_last_log_out", None)
                import time
                now = time.monotonic()
                if self._last_log_out is None:
                    self._last_log_out = now
                if now - self._last_log_out >= 1.0:
                    print(f"[Voice] OUT agente ~{self._bytes_out} bytes último ~1s")
                    self._bytes_out = 0
                    self._last_log_out = now
                yield chunk

    # ====== Internals =====

    async def _pump_events_to_queue(self):
        """
        Lee eventos/streams de la sesión Realtime y publica audio PCM16 en _audio_out_q.
        Intenta múltiples APIs comunes (stream_tts, audio_stream, etc.) y,
        si no están, itera eventos crudos con más logs.
        """
        # 1)Métodos típicos
        for mname in ("stream_tts", "audio_stream", "stream_agent_tts", "audio_out_stream"):
            maybe = getattr(self._session, mname, None)
            if callable(maybe):
                print(f"[Voice] DEBUG: usando stream '{mname}'")
                stream = maybe()
                if asyncio.iscoroutine(stream):
                    stream = await stream
                async for pcm in stream:
                    if pcm:
                        await self._audio_out_q.put(pcm)
                return  # si ese stream termina, salimos

        # 2) Intenta colas directas de salida
        for qname in ("audio_out", "pcm16_out", "tts_out"):
            q = getattr(self._session, qname, None)
            if q is not None:
                print(f"[Voice] DEBUG: leyendo de cola '{qname}'")
                while not self._closed:
                    pcm = await q.get()
                    if pcm:
                        await self._audio_out_q.put(pcm)
                return

        # 3) Itera eventos crudos y trata de extraer audio
        print("[Voice] DEBUG: no hay stream/cola directa; iterando eventos de sesión…")
        last_any = None
        async for ev in self._session:
            et = getattr(ev, "type", None)
            if et and et != last_any:
                print("[Voice] DEBUG ev.type:", et)
                last_any = et
            cand = None
            for attr in ("pcm16", "samples", "data", "buffer", "bytes", "audio", "chunk"):
                if hasattr(ev, attr):
                    cand = getattr(ev, attr)
                    break
            if cand is None:
                try:
                    cand = dict(ev)
                except Exception:
                    cand = None

            pcm = _to_pcm16_bytes(cand)
            if pcm:
                await self._audio_out_q.put(pcm)
            else:
                tname = type(cand).__name__ if cand is not None else "None"
                print(f"[Voice] DEBUG: evento sin PCM usable (tipo={tname})")

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
        print("[Voice] Realtime conectado (runner listo)")
        return SilverAIVoiceSession(inner_session)
