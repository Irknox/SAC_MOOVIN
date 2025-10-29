# - Logs coalescidos + FlowProbe
# - Pacing fijo a 20 ms
# - Modo ECO opcional (rebota audio sin pasar al agente)
# - Keep-alive de silencio mientras el agente "is_speaking()"
# - Flush inmediato al evento audio_interrupted
# - Contadores IN/OUT con snapshot periódico

import os, asyncio, socket, struct, time, contextlib
from collections import defaultdict
from SilverAI_Voice import SilverAIVoice
import audioop
from audioop import ulaw2lin, lin2ulaw
# ========= ENV =========
BIND_IP            = os.getenv("BIND_IP")
BIND_PORT          = int(os.getenv("BIND_PORT"))
RTP_PT             = int(os.getenv("RTP_PT"))      
LOG_LEVEL          = os.getenv("LOG_LEVEL", "INFO").upper()
ECHO_BACK          = os.getenv("ECHO_BACK", "0") == "1"
FRAME_MS           = int(os.getenv("FRAME_MS", "20"))   
SAMPLE_RATE = 8000
SAMPLES_PER_PKT = int(SAMPLE_RATE * (FRAME_MS/1000.0))   # 20 ms -> 160 a 8 kHz
BYTES_24K_PER_FRAME = int(24000 * (FRAME_MS/1000.0)) * 2   # p.ej. 20 ms -> 960 B a 24k PCM16
BYTES_8K_PER_FRAME  = SAMPLES_PER_PKT * 2  
# ========= LOGS =========
_LEVELS = ["ERROR", "WARN", "INFO", "DEBUG"]
_CUR_LVL = max(0, _LEVELS.index(LOG_LEVEL) if LOG_LEVEL in _LEVELS else 2)

def _ts(): return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
def log_err(*a): _CUR_LVL >= 0 and print(_ts(), "| ERROR |", *a, flush=True)
def log_warn(*a): _CUR_LVL >= 1 and print(_ts(), "| WARN  |", *a, flush=True)
def log_info(*a): _CUR_LVL >= 2 and print(_ts(), "| INFO  |", *a, flush=True)
def log_dbg(*a): _CUR_LVL >= 3 and print(_ts(), "| DEBUG |", *a, flush=True)


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
        self.voice = SilverAIVoice()
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

    # ---- Inbound: RTP PCMU -> SDK (usuario habla) ----
    async def rtp_inbound_task(self):
        log_info(f"RTP PCMU IN escuchando en {BIND_IP}:{BIND_PORT} PT={RTP_PT}")
        while not self._stop.is_set():
            pkt = await self.rtp.recv()
            if not pkt:
                continue

            # Manejar mensaje de control CALL_ENDED
            if pkt["payload"].startswith(b"CALL_ENDED"):
                log_info("[RTP] CALL_ENDED recibido, deteniendo el bridge")
                await self.cleanup_session()  # Cerrar la sesión del agente
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
                
    async def cleanup_session(self):
        """Cierra la sesión del agente y limpia el estado del bridge."""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)  # Cerrar sesión del agente
                log_info("[Bridge] Sesión del agente cerrada correctamente")
        except Exception as e:
            log_warn(f"Error cerrando la sesión del agente: {e}")
        finally:
            self.session = None
            async with self._buffer_lock:
                self.accum_out.clear() 
            self.accum_out.clear() 
            self.bytes_in = 0
            self.bytes_out = 0
            log_info("[Bridge] Estado limpiado tras desconexión")
            for task in asyncio.all_tasks():
                if task is not asyncio.current_task():
                    task.cancel()
            
    # ---- Outbound: SDK TTS 24k -> RTP PCMU (agente habla) ----
    async def sdk_tts_producer(self):
        """Produce audio desde el SDK y lo coloca en el buffer dinámico."""
        buf_24k = bytearray()
        pcm8k_buf = bytearray()
        ratecv_state = None

        async for pcm24 in self.session.stream_agent_tts():
            if self._stop.is_set():
                break
            if pcm24:
                buf_24k.extend(pcm24)

            # Convertir audio de 24k a 8k y μ-law
            while len(buf_24k) >= BYTES_24K_PER_FRAME:
                slice24 = bytes(buf_24k[:BYTES_24K_PER_FRAME])
                del buf_24k[:BYTES_24K_PER_FRAME]

                pcm8k, ratecv_state = audioop.ratecv(slice24, 2, 1, 24000, 8000, ratecv_state)
                pcm8k_buf.extend(pcm8k)

                while len(pcm8k_buf) >= BYTES_8K_PER_FRAME:
                    frame16 = bytes(pcm8k_buf[:BYTES_8K_PER_FRAME])
                    del pcm8k_buf[:BYTES_8K_PER_FRAME]

                    ulaw_frame = audioop.lin2ulaw(frame16, 2)
                    async with self._buffer_lock:
                        self.accum_out.extend(ulaw_frame)
                        
    async def rtp_pacer_loop(self):
        """Consume el buffer dinámico y envía los datos a intervalos regulares."""
        target_s = FRAME_MS / 1000.0
        SILENCE_ULAW = b"\x7F" * SAMPLES_PER_PKT
        next_deadline = time.monotonic() + target_s

        while not self._stop.is_set():
            now = time.monotonic()
            if now >= next_deadline:
                next_deadline += target_s
            else:
                await asyncio.sleep(next_deadline - now)
                next_deadline += target_s
            # Detectar el evento de flush
            if getattr(self.session, "_flush_tts_event", None) and self.session._flush_tts_event.is_set():
                async with self._buffer_lock:
                    self.accum_out.clear()  # Vaciar el buffer dinámico
                self.session._flush_tts_event.clear()
                log_info("[Bridge] FLUSH TTS detectado en rtp_pacer_loop")
                
            payload = None
            async with self._buffer_lock:
                if len(self.accum_out) >= SAMPLES_PER_PKT:
                    payload = bytes(self.accum_out[:SAMPLES_PER_PKT])
                    del self.accum_out[:SAMPLES_PER_PKT]

            if payload is None:
                payload = SILENCE_ULAW  # Enviar silencio si el buffer está vacío

            try:
                async with self._tx_lock:
                    await self.rtp.send_payload(payload)
                self.bytes_out += len(payload) + 12
                self.out_probe.note(len(payload) + 12)
                self.evlog.tick("out:rtp" if payload is not SILENCE_ULAW else "out:sil")
            except Exception as e:
                log_warn(f"Error enviando RTP: {e}")
                
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
        self.rtp.remote = None
        self.rtp.remote_learned = False
        self.rtp.seq = int.from_bytes(os.urandom(2), "big")
        self.rtp.ts = int(time.time() * SAMPLE_RATE) & 0xFFFFFFFF
        self.rtp.ssrc = struct.unpack("!I", os.urandom(4))[0]
        self.suppress_keepalive_until = 0.0
        log_info("[RTP] Reset aprendizaje destino para nueva llamada")
        log_info("Inicializando sesión SDK…")
        self.session = await self.voice.start()
        if hasattr(self.session, "set_on_audio_interrupted"):
            try:
                self.session.set_on_audio_interrupted(self.on_audio_interrupted)
                log_info("[Bridge] Callback on_audio_interrupted configurado")
            except Exception as e:
                log_warn(f"Error configurando callback on_audio_interrupted: {e}")

        log_info(f"RTP PCMU en {BIND_IP}:{BIND_PORT} PT={RTP_PT} SR={SAMPLE_RATE}Hz FRAME={FRAME_MS}ms")

        if ECHO_BACK:
            log_info("[Bridge] Modo ECO activo: rebotando audio, sin pasar al agente")
            tasks = [asyncio.create_task(self.rtp_inbound_task())]
        else:
            self.out_ulaw_queue = asyncio.Queue(maxsize=60)
            tasks = [
                asyncio.create_task(self.rtp_inbound_task()),
                asyncio.create_task(self.sdk_tts_producer()),
                asyncio.create_task(self.rtp_pacer_loop()),
            ]

        try:
            async with self.session:
                await asyncio.gather(*tasks)
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
