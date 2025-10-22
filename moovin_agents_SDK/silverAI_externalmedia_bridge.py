# Puente ExternalMedia (RTP Opus 48 kHz mono) <-> SilverAIVoiceSession (24 kHz)
# - Logs coalescidos + FlowProbe
# - Pacing fijo a 20 ms
# - Modo ECO opcional (rebota audio sin pasar al agente)
# - Keep-alive de silencio mientras el agente "is_speaking()"
# - Flush inmediato al evento audio_interrupted
# - Contadores IN/OUT con snapshot periódico

import os, asyncio, socket, struct, time, contextlib
from collections import defaultdict
from SilverAI_Voice import SilverAIVoice
import opuslib

# ========= ENV =========
BIND_IP            = os.getenv("BIND_IP")
BIND_PORT          = int(os.getenv("BIND_PORT"))
RTP_PT             = int(os.getenv("RTP_PT"))      
LOG_LEVEL          = os.getenv("LOG_LEVEL", "INFO").upper()
ECHO_BACK          = os.getenv("ECHO_BACK", "0") == "1"
FRAME_MS           = int(os.getenv("FRAME_MS", "20"))   
OPUS_SAMPLE_RATE   = int(os.getenv("OPUS_SAMPLE_RATE", "48000"))
OPUS_CHANNELS      = 2
OPUS_BITRATE       = int(os.getenv("OPUS_BITRATE", "160000")) 
OPUS_APP           = os.getenv("OPUS_APP", "voip")   

# ========= LOGS =========
_LEVELS = ["ERROR", "WARN", "INFO", "DEBUG"]
_CUR_LVL = max(0, _LEVELS.index(LOG_LEVEL) if LOG_LEVEL in _LEVELS else 2)

def _ts(): return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
def log_err(*a): _CUR_LVL >= 0 and print(_ts(), "| ERROR |", *a, flush=True)
def log_warn(*a): _CUR_LVL >= 1 and print(_ts(), "| WARN  |", *a, flush=True)
def log_info(*a): _CUR_LVL >= 2 and print(_ts(), "| INFO  |", *a, flush=True)
def log_dbg(*a): _CUR_LVL >= 3 and print(_ts(), "| DEBUG |", *a, flush=True)

APP_MAP = {
    "voip": opuslib.APPLICATION_VOIP,
    "audio": opuslib.APPLICATION_AUDIO,
    "restricted_lowdelay": opuslib.APPLICATION_RESTRICTED_LOWDELAY,
}


class CoalescedLogger:
    def __init__(self, tag="[EM Events]", window_ms=600):
        self.tag = tag
        self.window_s = window_ms / 1000.0
        self.b = defaultdict(int)
        self.t0 = time.monotonic()
    def tick(self, label: str):
        self.b[label] += 1
        now = time.monotonic()
        if now - self.t0 >= self.window_s:
            line = " | ".join(f"{k}({v})" for k,v in self.b.items())
            if line:
                print(self.tag, line, flush=True)
            self.b.clear(); self.t0 = now

class FlowProbe:
    def __init__(self, warmup_ms=1200):
        self.warmup_s = warmup_ms/1000.0
        self.first = None; self.prev = None
        self.intervals = []; self.sizes = []; self.done = False
    def note(self, size_b: int):
        now = time.monotonic()
        if self.first is None: self.first = now
        if self.prev is not None: self.intervals.append(now - self.prev)
        self.prev = now; self.sizes.append(size_b)
        if not self.done and (now - self.first) >= self.warmup_s:
            self.done = True; self._dump("Warmup")
    def _dump(self, title):
        if not self.sizes: return
        iv = self.intervals or [0.0]
        iv_mean = sum(iv)/len(iv); iv_min=min(iv); iv_max=max(iv)
        try: iv_p95 = sorted(iv)[int(0.95*len(iv))-1]
        except Exception: iv_p95 = iv_max
        print(f"[Bridge] {title}: packets={len(self.sizes)} "
              f"interval_mean={iv_mean*1000:.1f}ms p95={iv_p95*1000:.1f}ms "
              f"min={iv_min*1000:.1f}ms max={iv_max*1000:.1f}ms "
              f"size_mean={sum(self.sizes)/len(self.sizes):.1f}B "
              f"min={min(self.sizes)}B max={max(self.sizes)}B", flush=True)
    def dump_now(self, title="Snapshot"):
        self._dump(title)


# ========= RTP IO =========
class RtpIO:
    """RTP Opus 48 kHz mono. Symmetric RTP. 20 ms por paquete."""
    def __init__(self, bind_ip, bind_port, pt=111):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, bind_port))
        self.sock.setblocking(False)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        self.remote = None
        self.remote_learned = False 
        self.pt = pt & 0x7F
        self.ssrc = struct.unpack("!I", os.urandom(4))[0]
        self.seq  = int.from_bytes(os.urandom(2), "big")
        self.ts   = int(time.time() * OPUS_SAMPLE_RATE) & 0xFFFFFFFF
        self.frame_s = FRAME_MS / 1000.0
        
    def drain_nonblocking(self, max_bytes=1024*1024):
        """Lee en modo no bloqueante hasta agotar el socket o superar max_bytes.
        Devuelve (last_packet_bytes, last_addr, dropped_bytes)."""
        total = 0
        last = None; last_addr = None
        while True:
            try:
                chunk, addr = self.sock.recvfrom(2048) 
                last = chunk; last_addr = addr
                total += len(chunk)
                if total >= max_bytes:
                    break
            except BlockingIOError:
                break
        return last, last_addr, total

    async def recv(self):
        loop = asyncio.get_running_loop()
        data, addr = await loop.sock_recvfrom(self.sock, 2048)
        if not self.remote_learned:
            self.remote = addr
            self.remote_learned = True
            log_info(f"[RTP] Destino aprendido (1-shot): {addr[0]}:{addr[1]}")
        if len(data) < 12:
            return None
        v_p_x_cc, pt, seq, ts, ssrc = struct.unpack("!BBHII", data[:12])
        payload = data[12:]
        return {"pt": pt & 0x7F, "seq": seq, "ts": ts, "ssrc": ssrc, "payload": payload, "addr": addr}

    async def send_payload(self, opus_payload: bytes):
        if not self.remote_learned or not self.remote:
            return 
        hdr = struct.pack("!BBHII", 0x80, self.pt, self.seq & 0xFFFF,
                        self.ts & 0xFFFFFFFF, self.ssrc)
        pkt = hdr + opus_payload
        await asyncio.get_running_loop().sock_sendto(self.sock, pkt, self.remote)
        self.seq = (self.seq + 1) & 0xFFFF
        self.ts  = (self.ts + int(OPUS_SAMPLE_RATE * (FRAME_MS/1000.0))) & 0xFFFFFFFF

class OpusCodec:
    def __init__(self, sr=OPUS_SAMPLE_RATE, ch=OPUS_CHANNELS,
                 app=OPUS_APP, bitrate=OPUS_BITRATE):
        self.sr = sr
        self.ch = ch  # 2 para empatar opus/48000/2
        app_mode = APP_MAP.get(app, opuslib.APPLICATION_VOIP)
        self.dec = opuslib.Decoder(sr, self.ch)
        self.enc = opuslib.Encoder(sr, self.ch, app_mode)
        self.enc.bitrate = bitrate
        self.frame_size = int(sr * (FRAME_MS/1000.0))

    def decode(self, opus_payload: bytes) -> bytes:
        pcm = self.dec.decode(opus_payload, self.frame_size, decode_fec=False)
        if self.ch == 2:
            import array
            s = array.array('h', pcm)       
            m = array.array('h', [0]*(len(s)//2))
            j = 0
            for i in range(0, len(s), 2):
                m[j] = (int(s[i]) + int(s[i+1])) // 2
                j += 1
            return m.tobytes()
        return pcm

    def encode(self, pcm48_mono16: bytes) -> bytes:
        if self.ch == 2:
            import array
            m = array.array('h', pcm48_mono16)
            out = array.array('h', [0]*(len(m)*2))
            j = 0
            for i in range(len(m)):
                out[j] = m[i]; out[j+1] = m[i]
                j += 2
            return self.enc.encode(out.tobytes(), self.frame_size)
        return self.enc.encode(pcm48_mono16, self.frame_size)

# ========= BRIDGE =========
class ExternalMediaOpusBridge:
    def __init__(self):
        self.rtp = RtpIO(BIND_IP, BIND_PORT, RTP_PT)
        self.voice = SilverAIVoice()
        self.session = None
        self.opus = OpusCodec()
        self._stop = asyncio.Event()
        self._sdk_playing = False
        self.evlog = CoalescedLogger("[EM-Opus Events]", 600)
        self.in_probe = FlowProbe(1200)
        self.out_probe = FlowProbe(1200)
        self.bytes_in = 0
        self.bytes_out = 0
        self.last_log = time.monotonic()

    # ---- Inbound: RTP Opus -> SDK (usuario habla) ----
    async def rtp_inbound_task(self):
        log_info(f"RTP Opus IN escuchando en {BIND_IP}:{BIND_PORT} PT={RTP_PT}")
        while not self._stop.is_set():
            pkt = await self.rtp.recv()
            if not pkt: 
                continue
            last, addr_last, dropped = self.rtp.drain_nonblocking(max_bytes=1024*1024)
            if last is not None:
                pkt_bytes = last
                addr = addr_last
                if len(pkt_bytes) >= 12:
                    v_p_x_cc, pt, seq, ts, ssrc = struct.unpack("!BBHII", pkt_bytes[:12])
                    pkt = {"pt": pt & 0x7F, "seq": seq, "ts": ts, "ssrc": ssrc,
                        "payload": pkt_bytes[12:], "addr": addr}
                if dropped > 0:
                    log_warn(f"[RTP] Back-pressure: drenados {dropped}B; procesando último paquete")

            self.evlog.tick("in:rtp")
            self.in_probe.note(len(pkt["payload"]) + 12)
            self.bytes_in += len(pkt["payload"]) + 12

            if pkt["pt"] != RTP_PT:
                self.evlog.tick(f"pt:{pkt['pt']}")
                continue
            try:
                pcm48 = self.opus.decode(pkt["payload"])
            except Exception as e:
                log_warn(f"Opus decode error: {e}")
                continue

            if ECHO_BACK:
                try:
                    opus = self.opus.encode(pcm48)
                    await self.rtp.send_payload(opus)
                    self.bytes_out += len(opus) + 12
                    self.out_probe.note(len(opus) + 12)
                    self.evlog.tick("out:rtp")
                except Exception as e:
                    log_warn(f"ECO encode/send error: {e}")
                self._periodic_log()
                continue
            try:
                pcm24 = self.voice.resample_48k_to_24k(pcm48)
                await self.session.append_input_audio_24k(pcm24)
            except Exception as e:
                log_warn(f"append_input_audio_24k error: {e}")

            self._periodic_log()

    # ---- Outbound: SDK TTS 24k -> RTP Opus 48k (agente habla) ----
    async def sdk_tts_producer(self):
        """Lee TTS 24 kHz, convierte a 48 kHz, segmenta en 20 ms y envía con pacing."""
        log_dbg("sdk_tts_producer iniciado")
        frame_samples_48 = self.opus.frame_size 
        frame_bytes_48   = frame_samples_48 * 2  
        target_frame_s   = FRAME_MS / 1000.0

        async for pcm24 in self.session.stream_agent_tts():
            if pcm24 is None:
                continue
            self._sdk_playing = True
            pcm48 = self.voice.resample_24k_to_48k(pcm24)
            off = 0
            start = time.perf_counter()
            frames = 0
            while off < len(pcm48):
                chunk48 = pcm48[off:off+frame_bytes_48]
                if len(chunk48) < frame_bytes_48:
                    chunk48 = chunk48 + b"\x00" * (frame_bytes_48 - len(chunk48))
                off += len(chunk48)

                try:
                    opus_payload = self.opus.encode(chunk48)
                except Exception as e:
                    log_warn(f"Opus encode error: {e}")
                    continue

                await self.rtp.send_payload(opus_payload)
                self.bytes_out += len(opus_payload) + 12
                self.out_probe.note(len(opus_payload) + 12)
                self.evlog.tick("out:rtp")

                frames += 1
                target = frames * target_frame_s
                dt = time.perf_counter() - start
                if target > dt:
                    await asyncio.sleep(target - dt)

            self._periodic_log()

        self._sdk_playing = False
        log_dbg("sdk_tts_producer finalizado")

    # ---- Keep-alive de silencio cuando el agente habla ----
    async def keepalive_while_speaking(self):
        """Si el SDK reporta 'speaking', enviar silencio de 20 ms a tasa fija cuando no hay TTS activo.
        Mantiene timing del canal RTP en escenarios de pausas cortas."""
        frame_samples_48 = self.opus.frame_size
        silence48 = b"\x00" * (frame_samples_48 * 2)
        target_s = FRAME_MS / 1000.0
        while not self._stop.is_set():
            await asyncio.sleep(target_s)
            if getattr(self.session, "is_speaking", None) and self.session.is_speaking():
                try:
                    opus_payload = self.opus.encode(silence48)
                    await self.rtp.send_payload(opus_payload)
                    self.bytes_out += len(opus_payload) + 12
                    self.out_probe.note(len(opus_payload) + 12)
                    self.evlog.tick("out:sil")
                except Exception as e:
                    log_warn(f"keepalive encode/send error: {e}")
            self._periodic_log()

    async def on_audio_interrupted(self):
        """Si el SDK notifica interrupción, no hay cola aquí, pero respetamos trazas."""
        log_info("[Bridge] FLUSH TTS por audio_interrupted")
    def _periodic_log(self):
        now = time.monotonic()
        if now - self.last_log >= 1.0:
            if int(now) % 5 == 0:
                self.in_probe.dump_now("Snapshot-IN")
                self.out_probe.dump_now("Snapshot-OUT")
            print(f"[Bridge] IN={self.bytes_in}  OUT={self.bytes_out}  (último ~1s)", flush=True)
            self.bytes_in = 0; self.bytes_out = 0
            self.last_log = now

    # ---- Ciclo principal ----
    async def run(self):
        if ECHO_BACK:
            log_info("[Bridge] Modo ECO activo: rebotando audio, sin pasar al agente")

        log_info("Inicializando sesión SDK…")
        self.session = await self.voice.start()

        if hasattr(self.session, "set_on_audio_interrupted"):
            try:
                self.session.set_on_audio_interrupted(self.on_audio_interrupted)
            except Exception:
                pass

        log_info(f"RTP Opus en {BIND_IP}:{BIND_PORT} PT={RTP_PT} SR={OPUS_SAMPLE_RATE}Hz FRAME={FRAME_MS}ms")
        async with self.session:
            tasks = [
                asyncio.create_task(self.rtp_inbound_task()),
                asyncio.create_task(self.sdk_tts_producer()),
                asyncio.create_task(self.keepalive_while_speaking()),
            ]
            try:
                await asyncio.gather(*tasks)
            finally:
                self._stop.set()
        log_info("Bridge detenido")

# ========= MAIN =========
if __name__ == "__main__":
    try:
        asyncio.run(ExternalMediaOpusBridge().run())
    except KeyboardInterrupt:
        pass
