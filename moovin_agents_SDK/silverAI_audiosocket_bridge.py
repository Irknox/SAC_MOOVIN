# Puente AudioSocket (TCP) <-> SilverAIVoiceSession (PCM16 mono)
import asyncio
import struct
import time
import os
import audioop
from SilverAI_Voice import SilverAIVoice
from dotenv import load_dotenv
load_dotenv()
import contextlib

ECHO_BACK = os.getenv("ECHO_BACK", "0") == "1"

from collections import deque, defaultdict

class CoalescedLogger:
    def __init__(self, tag="[DBG]", window_ms=500):
        self.tag = tag
        self.window_ms = window_ms / 1000.0
        self._bucket = defaultdict(int)
        self._t0 = time.monotonic()

    def tick(self, label: str):
        self._bucket[label] += 1
        now = time.monotonic()
        if now - self._t0 >= self.window_ms:
            line = " | ".join(f"{k}({v})" for k, v in self._bucket.items())
            if line:
                print(f"{self.tag} {line}")
            self._bucket.clear()
            self._t0 = now

class FlowProbe:
    """Mide ráfaga inicial y stats corrientes."""
    def __init__(self, warmup_ms=1200):
        self.warmup_s = warmup_ms / 1000.0
        self._first_ts = None
        self._prev_ts = None
        self._intervals = []
        self._sizes = []
        self._done_warmup = False

    def note(self, size_bytes: int):
        now = time.monotonic()
        if self._first_ts is None:
            self._first_ts = now
        if self._prev_ts is not None:
            self._intervals.append(now - self._prev_ts)
        self._prev_ts = now
        self._sizes.append(size_bytes)

        if not self._done_warmup and (now - self._first_ts) >= self.warmup_s:
            self._done_warmup = True
            self._dump_warmup("Warmup")

    def _dump_warmup(self, title):
        if not self._sizes:
            return
        import statistics as stats
        iv = self._intervals or [0.0]
        sz = self._sizes
        iv_mean = sum(iv)/len(iv)
        iv_min = min(iv)
        iv_max = max(iv)
        try:
            iv_p95 = sorted(iv)[int(0.95*len(iv))-1]
        except Exception:
            iv_p95 = iv_max
        print(f"[Bridge] {title}: packets={len(sz)} "
              f"interval_mean={iv_mean*1000:.1f}ms p95={iv_p95*1000:.1f}ms min={iv_min*1000:.1f}ms max={iv_max*1000:.1f}ms "
              f"size_mean={sum(sz)/len(sz):.1f}B min={min(sz)}B max={max(sz)}B")

    def dump_now(self, title="Snapshot"):
        self._dump_warmup(title)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    print("[AudioSocket Bridge] cliente conectado")
    peer = writer.get_extra_info("peername") or ("?", 0)
    print(f"[AudioSocket Bridge] cliente conectado desde {peer}")
    evlog = CoalescedLogger(tag="[AudioSocket Events]", window_ms=600)
    in_probe = FlowProbe(warmup_ms=1200)
    out_probe = FlowProbe(warmup_ms=1200)

    bytes_in = 0      
    bytes_out = 0    
    last_log = time.monotonic()

        # === MODO ECO===
    if ECHO_BACK:
        print("[Bridge] Modo ECO activo: rebotando audio, sin pasar al agente")
        try:
            while True:
                # --- AudioSocket header (3 bytes): type + len_be ---
                hdr3 = await reader.readexactly(3)
                msg_type = hdr3[0]
                payload_len = (hdr3[1] << 8) | hdr3[2]

                payload = b""
                if payload_len:
                    payload = await reader.readexactly(payload_len)
                bytes_in += 3 + payload_len
                in_probe.note(3 + payload_len)
                evlog.tick(f"in:{msg_type:#04x}")
                if msg_type == 0x10 and payload:
                    writer.write(bytes([0x10, (payload_len >> 8) & 0xFF, payload_len & 0xFF]) + payload)
                    await writer.drain()
                    bytes_out += 3 + payload_len
                    out_probe.note(3 + payload_len)
                    evlog.tick(f"out:{msg_type:#04x}")

                now = time.monotonic()
                if now - last_log >= 1.0:
                    if int(now) % 5 == 0:
                        in_probe.dump_now("Snapshot-IN")
                        out_probe.dump_now("Snapshot-OUT")
                    print(f"[Bridge] IN={bytes_in}  OUT={bytes_out}  (último ~1s)")
                    bytes_in = 0
                    bytes_out = 0
                    last_log = now
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[AudioSocket Bridge] cliente desconectado {peer}")
        return
    
    # Levanta sesión con el agente (SDK Realtime)
    voice = SilverAIVoice()
    session = await voice.start()
    rate_state_out = None
    async with session:
        async def pump_agent_to_asterisk(session, writer):
            bytes_in = 0
            bytes_out = 0
            last_log = time.time()
            evlog = CoalescedLogger(tag="[AudioSocket Events]", window_ms=600)
            out_probe = FlowProbe(warmup_ms=1200)
            last_send = time.monotonic()
            
            
            SILENCE_20MS = b"\x00" * 320    
            TARGET_CHUNK_SEC = 0.020
            accum_out = bytearray()
            primed = False
            
            async def keepalive():
                nonlocal last_send, primed
                try:
                    while True:
                        await asyncio.sleep(0.02)
                        if not primed:
                            continue
                        if session.is_speaking() and len(accum_out) == 0:
                            if (time.monotonic() - last_send) > 0.06:
                                frame = bytes([0x10, 0x01, 0x40]) + SILENCE_20MS
                                writer.write(frame)
                                out_probe.note(len(frame)); evlog.tick("out:0x10")
                                await writer.drain()
                                last_send = time.monotonic()
                except asyncio.CancelledError:
                    pass

            ka_task = asyncio.create_task(keepalive())
            
            try:
                async for pcm8 in session.stream_agent_tts():
                    try:
                        if not pcm8:
                            continue
                        accum_out.extend(pcm8)
                        bytes_in += len(pcm8)
                        if not primed and len(accum_out) >= 320:
                            next_deadline = time.monotonic() + TARGET_CHUNK_SEC
                            for _ in range(2):
                                frame = bytes([0x10, 0x01, 0x40]) + SILENCE_20MS
                                writer.write(frame)
                                out_probe.note(len(frame)); evlog.tick("out:0x10")
                                await writer.drain()
                                bytes_out += len(frame)
                                await asyncio.sleep(TARGET_CHUNK_SEC)
                                next_deadline += TARGET_CHUNK_SEC
                            primed = True
                        while len(accum_out) >= 320:
                            chunk = bytes(accum_out[:320]); del accum_out[:320]
                            frame = bytes([0x10]) + struct.pack("!H", len(chunk)) + chunk
                            now_mono = time.monotonic()
                            if now_mono < next_deadline:
                                await asyncio.sleep(next_deadline - now_mono)
                            writer.write(frame)
                            out_probe.note(len(frame)); evlog.tick("out:0x10")
                            await writer.drain()
                            bytes_out += len(frame)
                            last_send = time.monotonic()
                            next_deadline += TARGET_CHUNK_SEC
                        max_accum = 320 * (12 if session.is_speaking() else 3)
                        if len(accum_out) > max_accum:
                            keep = max_accum
                            accum_out[:] = accum_out[-keep:]
                        now = time.time()
                        if now - last_log >= 1.0:
                            if int(time.monotonic()) % 5 == 0:
                                out_probe.dump_now("Snapshot-OUT")
                            print(f"[Bridge] IN={bytes_in}  OUT={bytes_out}  (último ~1s)")
                            bytes_in = 0
                            bytes_out = 0
                            last_log = now
                    except Exception as e:
                        print("[Bridge] error enviando audio a Asterisk:", repr(e))
                        break
            finally:
                ka_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await ka_task
                    
                    
        pump_task = asyncio.create_task(pump_agent_to_asterisk(session, writer))
        rate_state_in = None 
        try:
            while True:
                    hdr3 = await reader.readexactly(3)
                    msg_type = hdr3[0]
                    payload_len = (hdr3[1] << 8) | hdr3[2]
                    payload = b""
                    if payload_len:
                        payload = await reader.readexactly(payload_len)
                    bytes_in += 3 + payload_len
                    in_probe.note(3 + payload_len); evlog.tick(f"in:{msg_type:#04x}")
                    if msg_type == 0x01:
                        print(f"[Bridge] UUID: {payload.hex()}")
                        continue
                    if msg_type == 0x03:
                        print(f"[Bridge] DTMF: {payload!r}")
                        continue
                    if msg_type == 0x00:
                        break
                    if msg_type != 0x10:
                        continue
                    elif msg_type == 0x10:
                        ## Audio PCM16 8kHz mono
                        session.feed_pcm16(payload)
                    now = time.monotonic()
                    if now - last_log >= 1.0:
                        if int(time.monotonic()) % 5 == 0:
                            in_probe.dump_now("Snapshot-IN")
                        print(f"[Bridge] IN={bytes_in}  OUT={bytes_out}  (último ~1s)")
                        bytes_in = 0
                        bytes_out = 0
                        last_log = now

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            pump_task.cancel()
            try:
                await pump_task
            except asyncio.CancelledError:
                pass
            writer.close()
            await writer.wait_closed()
            print(f"[AudioSocket Bridge] cliente desconectado {peer}")


async def main():
    host = "0.0.0.0"
    port = int(os.getenv("AUDIOSOCKET_PORT", "40000"))
    server = await asyncio.start_server(handle_client, host, port)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"[AudioSocket Bridge] Escuchando en {addrs}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    # Ejecuta en modo no bloqueante
    asyncio.run(main())
