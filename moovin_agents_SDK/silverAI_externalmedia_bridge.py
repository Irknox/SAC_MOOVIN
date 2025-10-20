import os, asyncio, socket, struct, time, audioop
from collections import deque
from SilverAI_Voice import SilverAIVoice  

BIND_IP   = os.getenv("BIND_IP", "0.0.0.0")
BIND_PORT = int(os.getenv("BIND_PORT", "40010"))
RTP_PT    = int(os.getenv("RTP_PT", "109")) 
LOG_DEBUG = os.getenv("LOG_LEVEL", "info").lower() == "debug"

SAMPLES_PER_SEC_16K = 16000
FRAME_MS            = 20
SAMPLES_PER_FRAME   = int(SAMPLES_PER_SEC_16K * FRAME_MS / 1000)  # 320
BYTES_PER_FRAME     = SAMPLES_PER_FRAME * 2                       # 640

def log(*a): print("[EM-BRIDGE]", *a, flush=True)
def dbg(*a): 
    if LOG_DEBUG: print("[EM-BRIDGE][dbg]", *a, flush=True)

class RtpIO:
    """RTP L16 mono 16 kHz, 20 ms. Symmetric RTP."""
    def __init__(self, bind_ip, bind_port, pt=109):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, bind_port))
        self.sock.setblocking(False)
        self.remote = None
        self.pt = pt
        self.ssrc = struct.unpack("!I", os.urandom(4))[0]
        self.seq  = int.from_bytes(os.urandom(2), "big")
        self.ts   = int(time.time() * SAMPLES_PER_SEC_16K) & 0xFFFFFFFF

    async def recv(self):
        loop = asyncio.get_running_loop()
        data, addr = await loop.sock_recvfrom(self.sock, 2048)
        self.remote = addr
        if len(data) < 12: 
            return None
        v_p_x_cc, pt, seq, ts, ssrc = struct.unpack("!BBHII", data[:12])
        payload = data[12:]
        return {"pt": pt & 0x7F, "seq": seq, "ts": ts, "ssrc": ssrc, "payload": payload, "addr": addr}

    async def send_pcm16(self, pcm16_bytes):
        """Envía en frames de 20 ms (640 bytes) con pacing real."""
        if not self.remote:
            return  # aún no sabemos a dónde enviar
        t0 = time.perf_counter()
        off = 0
        frames = 0
        while off < len(pcm16_bytes):
            chunk = pcm16_bytes[off:off+BYTES_PER_FRAME]
            if len(chunk) < BYTES_PER_FRAME:
                chunk = chunk + b"\x00" * (BYTES_PER_FRAME - len(chunk))
            off += BYTES_PER_FRAME

            hdr = struct.pack("!BBHII",
                              0x80,            
                              self.pt & 0x7F,
                              self.seq & 0xFFFF,
                              self.ts & 0xFFFFFFFF,
                              self.ssrc)
            pkt = hdr + chunk
            await asyncio.get_running_loop().sock_sendto(self.sock, pkt, self.remote)
            self.seq = (self.seq + 1) & 0xFFFF
            self.ts  = (self.ts + SAMPLES_PER_FRAME) & 0xFFFFFFFF
            frames += 1
            target = frames * (FRAME_MS / 1000.0)
            dt = time.perf_counter() - t0
            sleep_time = target - dt
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

class ExternalMediaBridge:
    def __init__(self):
        self.rtp = RtpIO(BIND_IP, BIND_PORT, RTP_PT)
        self.voice = SilverAIVoice() 
        self.out_q = asyncio.Queue(maxsize=50) 
        self._stop = asyncio.Event()
        self._sdk_playing = False

    # ---- Inbound: RTP -> SDK (usuario habla) ----
    async def rtp_inbound_task(self):
        dbg("RTP inbound escuchando", BIND_IP, BIND_PORT)
        while not self._stop.is_set():
            pkt = await self.rtp.recv()
            if not pkt: 
                continue
            if len(pkt["payload"]) == 0:
                continue
            # Esperamos L16 mono 16 kHz desde ExternalMedia
            pcm16_16k = pkt["payload"]
            pcm16_24k = self.voice.resample_16k_to_24k(pcm16_16k)
            try:
                await self.voice.append_input_audio_24k(pcm16_24k)
            except Exception as e:
                dbg("append_input_audio_24k error:", e)

    # ---- Outbound: SDK TTS -> RTP (agente habla) ----
    async def sdk_tts_consumer(self):
        """Lee stream TTS 24 kHz del SDK, convierte y pone en cola RTP."""
        async for pcm24 in self.voice.stream_agent_tts():
            if pcm24 is None:
                continue
            self._sdk_playing = True
            pcm16 = self.voice.resample_24k_to_16k(pcm24)
            # Encolar por frames 20 ms
            off = 0
            while off < len(pcm16):
                chunk = pcm16[off:off+BYTES_PER_FRAME]
                off += len(chunk)
                # backpressure: si cola llena, descarta frames antiguos (preferimos latencia baja)
                if self.out_q.full():
                    try: _ = self.out_q.get_nowait()
                    except asyncio.QueueEmpty: pass
                await self.out_q.put(chunk)
        self._sdk_playing = False

    async def rtp_outbound_task(self):
        """Toma frames 20 ms de la cola y los envía por RTP con pacing exacto."""
        dbg("RTP outbound iniciado")
        while not self._stop.is_set():
            try:
                chunk = await asyncio.wait_for(self.out_q.get(), timeout=0.2)
            except asyncio.TimeoutError:
                # sin audio. No enviamos silencio por defecto
                continue
            await self.rtp.send_pcm16(chunk)

    # ---- Eventos del SDK relevantes ----
    async def on_audio_interrupted(self):
        """Cortar salida inmediata al detectar interrupción real del SDK."""
        # Vacía la cola de salida
        drained = 0
        while not self.out_q.empty():
            try:
                _ = self.out_q.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                break
        dbg(f"audio_interrupted -> flushed {drained} frames")

    # ---- Ciclo principal ----
    async def run(self):
        log("Inicializando sesión SDK…")
        await self.voice.start_session(
            input_audio_format={"type": "audio/pcm", "rate": 24000},
            output_audio_format={"type": "audio/pcm", "rate": 24000},
            on_audio_interrupted=self.on_audio_interrupted
        )

        log(f"RTP L16/16k en {BIND_IP}:{BIND_PORT} PT={RTP_PT}")
        tasks = [
            asyncio.create_task(self.rtp_inbound_task()),
            asyncio.create_task(self.sdk_tts_consumer()),
            asyncio.create_task(self.rtp_outbound_task()),
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            self._stop.set()
            await self.voice.close_session()
            log("Bridge detenido")

if __name__ == "__main__":
    try:
        asyncio.run(ExternalMediaBridge().run())
    except KeyboardInterrupt:
        pass
