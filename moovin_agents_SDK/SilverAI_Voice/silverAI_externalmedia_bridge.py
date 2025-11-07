import os, asyncio, socket, struct, time, contextlib
from collections import defaultdict
from SilverAI_Voice import SilverAIVoice
import audioop
from audioop import ulaw2lin, lin2ulaw
from config import create_mysql_pool, create_tools_pool
import numpy as np

try:
    import soxr  
    _HAS_SOXR = True
except Exception:
    _HAS_SOXR = False   
    import samplerate # pyright: ignore[reportMissingImports]

# ========= ENV =========
BIND_IP            = os.getenv("BIND_IP")
BIND_PORT          = int(os.getenv("BIND_PORT"))
RTP_PT             = int(os.getenv("RTP_PT"))      
LOG_LEVEL          = os.getenv("LOG_LEVEL", "INFO").upper()
ECHO_BACK          = os.getenv("ECHO_BACK", "0") == "1"
FRAME_MS           = int(os.getenv("FRAME_MS", "20"))   
LPF_8K          = os.getenv("LPF_8K", "0") == "1"
DE_ESSER        = os.getenv("DE_ESSER", "0") == "1"
DE_ESSER_AMOUNT = float(os.getenv("DE_ESSER_AMOUNT", "0.20"))
SAMPLE_RATE = 8000
SAMPLES_PER_PKT = int(SAMPLE_RATE * (FRAME_MS/1000.0))   # 20 ms -> 160 a 8 kHz
BYTES_24K_PER_FRAME = int(24000 * (FRAME_MS/1000.0)) * 2   # 20 ms -> 960 B a 24k PCM16
BYTES_8K_PER_FRAME  = SAMPLES_PER_PKT * 2  
PRE_ROLL            = os.getenv("PRE_ROLL", "1") == "1"
PRE_ROLL_FRAMES     = int(os.getenv("PRE_ROLL_FRAMES", "1"))
FADE_IN_FRAMES      = int(os.getenv("FADE_IN_FRAMES", "2"))
AGC_ENABLE        = os.getenv("AGC_ENABLE", "1") == "1"
AGC_TARGET_RMS    = int(os.getenv("AGC_TARGET_RMS", "4000"))

COMPRESS_RATIO    = float(os.getenv("COMPRESS_RATIO", "1.6"))   # 1.5–2.0
LIMIT_MAX         = int(os.getenv("LIMIT_MAX", "30000")) 

GAIN_ENABLE       = os.getenv("GAIN_ENABLE", "1") == "1"
GAIN_DB           = float(os.getenv("GAIN_DB"))    
GAIN_MAX_DB       = float(os.getenv("GAIN_MAX_DB")) 
DITHER_LEVEL_LSB  = int(os.getenv("DITHER_LEVEL_LSB")) 

COMPRESS_ENABLE   = os.getenv("COMPRESS_ENABLE", "0") == "1"  
DITHER_ENABLE     = os.getenv("DITHER_ENABLE", "0") == "1"    

SOFTCLIP_ENABLE   = os.getenv("SOFTCLIP_ENABLE", "1") == "1"
# ========= LOGS =========
_LEVELS = ["ERROR", "WARN", "INFO", "DEBUG"]
_CUR_LVL = max(0, _LEVELS.index(LOG_LEVEL) if LOG_LEVEL in _LEVELS else 2)

def _ts(): return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
def log_err(*a): _CUR_LVL >= 0 and print(_ts(), "| ERROR |", *a, flush=True)
def log_warn(*a): _CUR_LVL >= 1 and print(_ts(), "| WARN  |", *a, flush=True)
def log_info(*a): _CUR_LVL >= 2 and print(_ts(), "| INFO  |", *a, flush=True)
def log_dbg(*a): _CUR_LVL >= 3 and print(_ts(), "| DEBUG |", *a, flush=True)


async def init_resources():
    preloaded_resources={
    "tools": create_tools_pool,
    "mysql": create_mysql_pool,   
    }
        
    resources = {}
    for name, resource in preloaded_resources.items():
        response = await resource()
        if response:
            resources[name] = response
    return resources

def _lpf_8k_simple_state(pcm: bytes, alpha: float = 0.715, y0: int = 0):
    """
    LPF unipolo con estado entre frames.
    Recibe y_prev (y0) y devuelve (pcm_filtrado, y_last).
    """
    if not pcm:
        return pcm, y0
    import array
    arr = array.array("h")
    arr.frombytes(pcm)
    y = int(y0)
    for i, x in enumerate(arr):
        y = int(y + alpha * (x - y))
        if y > 32767: y = 32767
        if y < -32768: y = -32768
        arr[i] = y
    return arr.tobytes(), y

def _soft_de_esser_pcm16_state(pcm: bytes, amount: float = 0.68, y_prev: float = 0.0):
    """
    De-esser suave con estado entre frames.
    Recibe y_prev y devuelve (pcm_filtrado, y_last).
    """
    if not pcm:
        return pcm, y_prev
    import struct
    nsamp = len(pcm) // 2
    if nsamp == 0:
        return pcm, y_prev
    it = struct.iter_unpack("<h", pcm)
    out = bytearray(len(pcm))
    w = memoryview(out)
    a = max(0.0, min(0.45, amount))
    one_minus = 1.0 - a
    y = float(y_prev)
    idx = 0
    for (x,) in it:
        y = one_minus * x + a * y
        mixed = 0.22 * y + 0.78 * x
        if mixed > 32767: mixed = 32767
        if mixed < -32768: mixed = -32768
        struct.pack_into("<h", w, idx, int(mixed))
        idx += 2
    return bytes(out), y


def _agc_rms(frame: bytes, target_rms: int) -> bytes:
    import audioop
    rms = audioop.rms(frame, 2)
    if rms == 0:
        return frame
    gain = target_rms / rms
    if gain > 3.0:
        gain = 3.0
    return audioop.mul(frame, 2, gain)

def _soft_compress_and_limit(frame: bytes, ratio: float, limit_max: int) -> bytes:
    import struct
    out = bytearray(len(frame))
    mv = memoryview(out)
    idx = 0
    thr = 18000
    for (s,) in struct.iter_unpack("<h", frame):
        x = s
        if x > thr:
            over = x - thr
            x = int(thr + over / ratio)
        elif x < -thr:
            over = x + thr
            x = int(-thr + over / ratio)
        if x > limit_max: x = limit_max
        if x < -limit_max: x = -limit_max
        struct.pack_into("<h", mv, idx, x)
        idx += 2
    return bytes(out)

def _soft_clip_tanh_int16(frame: bytes, out_limit: int = 32100, drive: float = 1.2) -> bytes:
    """Soft-clip suave tipo tanh para picos transitorios, evita raspado al pasar a μ-law."""
    if not frame:
        return frame
    import numpy as np
    x = np.frombuffer(frame, dtype="<i2").astype(np.float32)
    xf = x / 32768.0
    y = np.tanh(drive * xf)
    y_int = (y * out_limit).astype("<i2")
    return y_int.tobytes()

def _lpf_8k_simple(pcm: bytes, alpha: float = 0.715) -> bytes:
    if not pcm:
        return pcm
    import array
    arr = array.array("h")
    arr.frombytes(pcm)
    y = 0
    for i, x in enumerate(arr):
        y = int(y + alpha * (x - y))
        if y > 32767: y = 32767
        if y < -32768: y = -32768
        arr[i] = y
    return arr.tobytes()

def _hard_limit_int16(frame: bytes, limit_max: int = 30000) -> bytes:
    import struct
    out = bytearray(len(frame))
    mv = memoryview(out)
    idx = 0
    for (s,) in struct.iter_unpack("<h", frame):
        x = s
        if x >  limit_max: x =  limit_max
        if x < -limit_max: x = -limit_max
        struct.pack_into("<h", mv, idx, x)
        idx += 2
    return bytes(out)

def _soft_de_esser_pcm16(pcm: bytes, amount: float = 0.68) -> bytes:
    if not pcm:
        return pcm
    import struct
    nsamp = len(pcm) // 2
    if nsamp == 0:
        return pcm
    it = struct.iter_unpack("<h", pcm)
    out = bytearray(len(pcm))
    w = memoryview(out)
    y_prev = 0.0
    a = max(0.0, min(0.45, amount))
    one_minus = 1.0 - a
    idx = 0
    for (x,) in it:
        y = one_minus * x + a * y_prev
        mixed = 0.22 * y + 0.78 * x
        if mixed > 32767: mixed = 32767
        if mixed < -32768: mixed = -32768
        struct.pack_into("<h", w, idx, int(mixed))
        idx += 2
        y_prev = y
    return bytes(out)

def _apply_gain_db(frame: bytes, db: float, max_db: float) -> bytes:
    """Ganancia fija en dB con tope. Evita AGC/compresores; solo sube nivel."""
    import audioop, math
    if not frame or db == 0.0:
        return frame
    db = max(-max_db, min(max_db, db))
    gain = math.pow(10.0, db/20.0)
    return audioop.mul(frame, 2, gain)

def _dither_tpdf_int16(frame: bytes, level_lsb: int = 1) -> bytes:
    """
    Dither TPDF muy pequeño antes de μ-law para suavizar la cuantización.
    level_lsb = 1 añade ruido triangular ~±1 LSB (int16).
    """
    if not frame or level_lsb <= 0:
        return frame
    import struct, random
    out = bytearray(len(frame))
    mv = memoryview(out)
    scale = level_lsb  # en LSBs de int16
    idx = 0
    for (s,) in struct.iter_unpack("<h", frame):
        # TPDF: (U1 + U2 - 1) * escala ; U ~ Uniforme[0,1)
        n = (random.random() + random.random() - 1.0) * scale
        x = int(s + n)
        if x > 32767: x = 32767
        if x < -32768: x = -32768
        struct.pack_into("<h", mv, idx, x)
        idx += 2
    return bytes(out)

def _fade_in_pcm16(frame: bytes, step: int, total: int) -> bytes:
    if total <= 1:
        return frame
    import struct
    fac_start = 0.15 
    fac_end = 1.0
    t = step / (total - 1)
    fac = fac_start + (fac_end - fac_start) * t
    out = bytearray(len(frame))
    mv = memoryview(out)
    idx = 0
    for (sample,) in struct.iter_unpack("<h", frame):
        v = int(sample * fac)
        if v > 32767: v = 32767
        if v < -32768: v = -32768
        struct.pack_into("<h", mv, idx, v)
        idx += 2
    return bytes(out)

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
    """RTP PCMU (G.711 μ-law) 8 kHz. Symmetric RTP. 20 ms por paquete."""
    def __init__(self, bind_ip, bind_port, pt=111):
        self.last_rx_addr = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_ip, bind_port))
        self.sock.setblocking(False)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        self.remote = None
        self.remote_learned = False 
        self.pt = pt & 0x7F
        self.ssrc = struct.unpack("!I", os.urandom(4))[0]
        self.seq  = int.from_bytes(os.urandom(2), "big")
        self.ts = int(time.time() * SAMPLE_RATE) & 0xFFFFFFFF
        self.frame_s = FRAME_MS / 1000.0
        self.echo_enabled = bool(int(os.getenv("ECHO_BACK", "0")))
        self.tx_queue = asyncio.Queue(maxsize=200)
        self.last_rx_ts = None
        self.pacer_task = None
        
    async def send_payload_with_headers(self, payload: bytes, pt: int, seq: int, ts: int, ssrc: int):
        if not self.remote_learned or not self.remote:
            return
        hdr = struct.pack("!BBHII", 0x80, pt & 0x7F, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc)
        pkt = hdr + payload
        await asyncio.get_running_loop().sock_sendto(self.sock, pkt, self.remote)
    
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
        self.last_rx_addr = addr
        if data.startswith(b"CALL_ENDED"):
            log_info(f"[RTP] CALL_ENDED recibido desde {addr}")
            return {"payload": b"CALL_ENDED"}
        if data.startswith(b"CTRL "):
            try:
                txt = data.decode("utf-8").strip()[5:]
                ip, port_s = txt.split(":")
                ctrl_ip = ip
                ctrl_port = int(port_s)
                if ctrl_ip.startswith("127.") and self.last_rx_addr:
                    log_info(f"[RTP] CTRL loopback {ctrl_ip} detectado; usando {self.last_rx_addr[0]} como destino real")
                    ctrl_ip = self.last_rx_addr[0]
                self.remote = (ctrl_ip, ctrl_port)
                self.remote_learned = True
                self.seq  = int.from_bytes(os.urandom(2), "big")
                self.ts = int(time.time() * SAMPLE_RATE) & 0xFFFFFFFF
                self.ssrc = struct.unpack("!I", os.urandom(4))[0]
                log_info(f"[RTP] Destino FORZADO por control: {ip}:{port_s}")
            except Exception as e:
                log_warn(f"[RTP] CTRL inválido: {e}")
            return None
        if not self.remote_learned:
            self.remote = addr
            self.remote_learned = True
            log_info(f"[RTP] Destino aprendido (1-shot): {addr[0]}:{addr[1]}")
        if len(data) < 12:
            return None
        v_p_x_cc, pt, seq, ts, ssrc = struct.unpack("!BBHII", data[:12])
        payload = data[12:]
        return {"pt": pt & 0x7F, "seq": seq, "ts": ts, "ssrc": ssrc, "payload": payload, "addr": addr}

    async def send_payload(self, payload: bytes):
        if not self.remote_learned or not self.remote:
            return 
        hdr = struct.pack("!BBHII", 0x80, self.pt, self.seq & 0xFFFF,
                        self.ts & 0xFFFFFFFF, self.ssrc)
        pkt = hdr + payload
        await asyncio.get_running_loop().sock_sendto(self.sock, pkt, self.remote)
        self.seq = (self.seq + 1) & 0xFFFF
        self.ts = (self.ts + SAMPLES_PER_PKT) & 0xFFFFFFFF


# ========= BRIDGE =========
class ExtermalMediaBridge:
    def __init__(self):
        self.rtp = RtpIO(BIND_IP, BIND_PORT, RTP_PT)
        self.voice = None
        self.session = None
        self._stop = asyncio.Event()
        self._sdk_playing = False
        self.evlog = CoalescedLogger("[EM Events]", 600)
        self.in_probe = FlowProbe(1200)
        self.out_probe = FlowProbe(1200)
        self._echo_synced = False
        self.bytes_in = 0
        self.bytes_out = 0
        self.last_log = time.monotonic()
        self._reset_pacer_deadline = False
        self._tx_lock = asyncio.Lock()
        self.accum_out = bytearray()  
        self._buffer_lock = asyncio.Lock() 
        self.session_tasks = []
        self.call_started_at = None   
        self.resampler_24k_to_8k = None   
        
        if _HAS_SOXR:
            self.resampler_24k_to_8k = soxr.ResampleStream(
                24000, 8000, channels=1, dtype="int16",
                quality="VHQ",
                phase_response=50,
                rolloff="low"  
            )
        else:
            self.resampler_24k_to_8k = samplerate.Resampler("sinc_best")
    # ---- Inbound: RTP PCMU -> SDK (usuario habla) ----
    async def rtp_inbound_task(self):
        log_info(f"RTP PCMU IN escuchando en {BIND_IP}:{BIND_PORT} PT={RTP_PT}")
        try:
            while not self._stop.is_set():
                pkt = await self.rtp.recv()
                if not pkt:
                    continue

                if pkt["payload"].startswith(b"CALL_ENDED"):
                    log_info("[RTP] CALL_ENDED recibido, deteniendo el bridge")
                    async with self._buffer_lock:
                        self.accum_out.clear() 
                    await self.cleanup_session() 
                    self._stop.set()
                    break
                if self.call_started_at and (time.monotonic() - self.call_started_at) > (55 * 60):
                    log_warn("[Bridge] Llamada superó 55 minutos. Cerrando sesión y deteniendo bridge.")
                    await self.cleanup_session()
                    self._stop.set()
                    break

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

                if not getattr(self.rtp, "_pt_locked", False):
                    self.rtp.pt = pkt["pt"]
                    self.rtp._pt_locked = True
                    log_info(f"[RTP] PT de salida fijado a {self.rtp.pt} por aprendizaje")
                elif pkt["pt"] != self.rtp.pt:
                    self.evlog.tick(f"pt_mismatch:{pkt['pt']}")
                    continue

                if not getattr(self.rtp, "_ts_locked", False):
                    self.rtp.ts = pkt["ts"]
                    self.rtp._ts_locked = True
                    log_info(f"[RTP] TS de salida alineado a {self.rtp.ts}")

                if ECHO_BACK:
                    try:
                        async with self._tx_lock:
                            await self.rtp.send_payload_with_headers(
                                pkt["payload"], pkt["pt"], pkt["seq"], pkt["ts"], pkt["ssrc"]
                            )
                        plen = len(pkt["payload"])
                        self.bytes_out += plen + 12
                        self.out_probe.note(plen + 12)
                        self.evlog.tick("out:rtp")
                    except Exception as e:
                        log_warn(f"ECO send error: {e}")
                    self._periodic_log()
                    continue
                else:
                    try:
                        pcm8k = audioop.ulaw2lin(pkt["payload"], 2)
                        try:
                            self.session.feed_pcm16(pcm8k)
                            self.evlog.tick("to:sdk")
                        except Exception as e:
                            log_warn(f"feed_pcm16 error: {e}")
                    except Exception as e:
                        log_warn(f"append_input_audio_24k error: {e}")

                    self._periodic_log()
        except asyncio.CancelledError:
            log_info("[RTP] Tarea rtp_inbound_task cancelada")      
            
    async def cleanup_session(self):
        """Cierra la sesión del agente y limpia el estado del bridge."""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None) 
                log_info("[Bridge] Sesión del agente cerrada correctamente")
        except Exception as e:
            log_warn(f"Error cerrando la sesión del agente: {e}")
        finally:
            self.session = None
            async with self._buffer_lock:
                self.accum_out.clear() 
            self.bytes_in = 0
            self.bytes_out = 0
            self.suppress_keepalive_until = 0.0
            self._sdk_playing = False
            log_info("[Bridge] Estado limpiado tras desconexión")

            for task in self.session_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        log_info(f"[Bridge] Tarea {task.get_name()} cancelada correctamente")
            self.session_tasks.clear()  
                    
    # ---- Outbound: SDK TTS 24k -> RTP PCMU (agente habla) ----
    async def sdk_tts_producer(self):
        """Produce audio desde el SDK y lo coloca en el buffer dinámico."""
        buf_24k = bytearray()
        pcm8k_buf = bytearray()
        ratecv_state = None
        first_frames_to_fade = 0
        is_new_phrase = False
        lpf_y_last = 0         
        deess_y_last = 0.0  
        try:
            async for pcm24 in self.session.stream_agent_tts():
                if self._stop.is_set():
                    break
                if pcm24:
                    buf_24k.extend(pcm24)

                # Convertir audio de 24k a 8k y μ-law
                while len(buf_24k) >= BYTES_24K_PER_FRAME:
                    slice24 = bytes(buf_24k[:BYTES_24K_PER_FRAME])
                    del buf_24k[:BYTES_24K_PER_FRAME]

                    pcm24_i16 = np.frombuffer(slice24, dtype="<i2")

                    if _HAS_SOXR:
                        pcm8_i16 = self.resampler_24k_to_8k.process(pcm24_i16)
                    else:
                        pcm24_f32 = pcm24_i16.astype(np.float32) / 32768.0
                        pcm8_f32  = self.resampler_24k_to_8k.process(pcm24_f32)
                        pcm8_i16  = (pcm8_f32 * 32768.0).clip(-32768, 32767).astype("<i2")

                    pcm8k = pcm8_i16.tobytes()
                    pcm8k_buf.extend(pcm8k)
                    was_empty_8k = (len(pcm8k_buf) == 0)
                    pcm8k = pcm8_int16.tobytes()
                    pcm8k_buf.extend(pcm8k)
                    if was_empty_8k:
                        is_new_phrase = True
                        first_frames_to_fade = FADE_IN_FRAMES
                        
                    while len(pcm8k_buf) >= BYTES_8K_PER_FRAME:
                        frame16 = bytes(pcm8k_buf[:BYTES_8K_PER_FRAME])
                        del pcm8k_buf[:BYTES_8K_PER_FRAME]

                        if LPF_8K:
                            frame16, lpf_y_last = _lpf_8k_simple_state(frame16, 0.69, lpf_y_last)
                        if DE_ESSER:
                            frame16, deess_y_last = _soft_de_esser_pcm16_state(frame16, DE_ESSER_AMOUNT, deess_y_last)

                        if first_frames_to_fade > 0:
                            frame16 = _fade_in_pcm16(
                                frame16, FADE_IN_FRAMES - first_frames_to_fade, FADE_IN_FRAMES
                            )
                            first_frames_to_fade -= 1
                            
                        if GAIN_ENABLE and GAIN_DB != 0.0:
                            frame16 = _apply_gain_db(frame16, GAIN_DB, GAIN_MAX_DB)
                            
                        if SOFTCLIP_ENABLE:
                            frame16 = _soft_clip_tanh_int16(frame16, out_limit=LIMIT_MAX, drive=1.0)
                        else:
                            frame16 = _hard_limit_int16(frame16, LIMIT_MAX)
                        
                        if DITHER_ENABLE and DITHER_LEVEL_LSB > 0:
                            frame16 = _dither_tpdf_int16(frame16, level_lsb=DITHER_LEVEL_LSB)

                        ulaw_frame = audioop.lin2ulaw(frame16, 2)
                        async with self._buffer_lock:
                            self.accum_out.extend(ulaw_frame)
        except asyncio.CancelledError:
            log_info("[RTP] Tarea rtp_inbound_task cancelada")          
                  
    async def rtp_pacer_loop(self):
        """Consume el buffer dinámico y envía los datos a intervalos regulares."""
        target_s = FRAME_MS / 1000.0
        SILENCE_ULAW = b"\x7F" * SAMPLES_PER_PKT
        next_deadline = time.monotonic() + target_s
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                if now >= next_deadline:
                    next_deadline += target_s
                else:
                    await asyncio.sleep(next_deadline - now)
                    next_deadline += target_s

                if getattr(self.session, "_flush_tts_event", None) and self.session._flush_tts_event.is_set():
                    async with self._buffer_lock:
                        self.accum_out.clear() 
                    self.session._flush_tts_event.clear()
                    log_info("[Bridge] FLUSH TTS detectado en rtp_pacer_loop")
                    
                payload = None
                async with self._buffer_lock:
                    if len(self.accum_out) >= SAMPLES_PER_PKT:
                        payload = bytes(self.accum_out[:SAMPLES_PER_PKT])
                        del self.accum_out[:SAMPLES_PER_PKT]

                if payload is None:
                    payload = SILENCE_ULAW 

                try:
                    async with self._tx_lock:
                        await self.rtp.send_payload(payload)
                    self.bytes_out += len(payload) + 12
                    self.out_probe.note(len(payload) + 12)
                    self.evlog.tick("out:rtp" if payload is not SILENCE_ULAW else "out:sil")
                except Exception as e:
                    log_warn(f"Error enviando RTP: {e}")
        except asyncio.CancelledError:
            log_info("[RTP] Tarea rtp_inbound_task cancelada")         
                    
    # ---- Keep-alive de silencio cuando el agente habla ----
    async def keepalive_while_speaking(self):
        if ECHO_BACK:
            return
        target_s = FRAME_MS / 1000.0
        silence = b"\x7F" * SAMPLES_PER_PKT

        while not self._stop.is_set():
            await asyncio.sleep(target_s)
            if getattr(self, "_sdk_playing", False):
                continue
            if getattr(self.session, "is_speaking", None) and self.session.is_speaking():
                    if getattr(self, "suppress_keepalive_until", 0.0) and time.monotonic() < self.suppress_keepalive_until:
                        continue
                    try:
                        async with self._tx_lock:
                            await self.rtp.send_payload(silence)
                        self.bytes_out += len(silence) + 12
                        self.out_probe.note(len(silence) + 12)
                        self.evlog.tick("out:sil")
                    except Exception as e:
                        log_warn(f"keepalive send error: {e}")
            self._periodic_log()


    async def on_audio_interrupted(self):
        """Flush inmediato del backlog TTS y supresión breve del keep-alive."""
        try:
            async with self._buffer_lock:
                self.accum_out.clear()  # Vaciar el buffer dinámico
            self.suppress_keepalive_until = time.monotonic() + 0.20
            log_info("[Bridge] FLUSH TTS por audio_interrupted: buffer vaciado")
        except Exception as e:
            log_warn(f"on_audio_interrupted error: {e}")


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
        while True: 
            self._stop.clear()           
            self.session_tasks = []        
            self.call_started_at = time.monotonic()  
            self.rtp.remote = None
            self.rtp.remote_learned = False
            self.rtp.seq = int.from_bytes(os.urandom(2), "big")
            self.rtp.ts = int(time.time() * SAMPLE_RATE) & 0xFFFFFFFF
            self.rtp.ssrc = struct.unpack("!I", os.urandom(4))[0]
            self.suppress_keepalive_until = 0.0
            log_info("[RTP] Reset aprendizaje destino para nueva llamada")

            resources = await init_resources()
            self.voice = SilverAIVoice(resources) 
            self.session = await self.voice.start()  
            log_info("Sesión SilverAI Iniciada…")
            if hasattr(self.session, "set_on_audio_interrupted"):
                try:
                    self.session.set_on_audio_interrupted(self.on_audio_interrupted)
                    log_info("[Bridge] Callback on_audio_interrupted configurado")
                except Exception as e:
                    log_warn(f"Error configurando callback on_audio_interrupted: {e}")

            log_info(f"RTP PCMU en {BIND_IP}:{BIND_PORT} PT={RTP_PT} SR={SAMPLE_RATE}Hz FRAME={FRAME_MS}ms")

            tasks = [
                asyncio.create_task(self.rtp_inbound_task(), name="rtp_inbound_task"),
                asyncio.create_task(self.sdk_tts_producer(), name="sdk_tts_producer"),
                asyncio.create_task(self.rtp_pacer_loop(), name="rtp_pacer_loop"),
            ]
            self.session_tasks.extend(tasks) 

            try:
                async with self.session:
                    await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                log_info("[Bridge] Tareas canceladas correctamente")
            except Exception as e:
                log_err(f"Error en el ciclo principal: {e}")
            finally:
                self._stop.set()
                await self.cleanup_session()
                log_info("Bridge detenido")

# ========= MAIN =========
if __name__ == "__main__":
    try:
        asyncio.run(ExtermalMediaBridge().run())
    except KeyboardInterrupt:
        pass