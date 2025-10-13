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

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    print("[AudioSocket Bridge] cliente conectado")
    peer = writer.get_extra_info("peername") or ("?", 0)
    print(f"[AudioSocket Bridge] cliente conectado desde {peer}")

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
                if msg_type == 0x10 and payload:
                    writer.write(bytes([0x10, (payload_len >> 8) & 0xFF, payload_len & 0xFF]) + payload)
                    await writer.drain()
                    bytes_out += 3 + payload_len

                now = time.monotonic()
                if now - last_log >= 1.0:
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

            last_send = time.monotonic()
            SILENCE_20MS = b"\x00" * 320
            next_deadline = last_send
            TARGET_CHUNK_SEC = 0.020 
            
            async def keepalive():
                nonlocal last_send
                try:
                    while True:
                        await asyncio.sleep(0.02) 
                        if session.is_speaking():
                            if (time.monotonic() - last_send) > 0.06: 
                                frame = bytes([0x10, 0x01, 0x40]) + SILENCE_20MS  
                                writer.write(frame)
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
                        if 'accum_out' not in locals():
                            accum_out = bytearray()
                        if 'next_deadline' not in locals():
                            next_deadline = time.monotonic()
                        accum_out.extend(pcm8)
                        while len(accum_out) >= 320:
                            chunk = bytes(accum_out[:320])
                            del accum_out[:320]
                            frame = bytes([0x10]) + struct.pack("!H", len(chunk)) + chunk
                            now_mono = time.monotonic()
                            if now_mono < next_deadline:
                                await asyncio.sleep(next_deadline - now_mono)

                            writer.write(frame)
                            await writer.drain()
                            bytes_out += len(frame)
                            next_deadline += 0.020
                        max_accum = 320 * 3
                        if len(accum_out) > max_accum:
                            overflow = len(accum_out) - max_accum
                            del accum_out[:overflow]
                        now = time.time()
                        if now - last_log >= 1.0:
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
