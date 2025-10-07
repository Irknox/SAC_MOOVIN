# Puente AudioSocket (TCP) <-> SilverAIVoiceSession (PCM16 mono)
import asyncio
import struct
import time
import os

from dotenv import load_dotenv
from SilverAI_Voice import SilverAIVoice

load_dotenv()


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    print("[AudioSocket Bridge] cliente conectado")
    peer = writer.get_extra_info("peername") or ("?", 0)
    print(f"[AudioSocket Bridge] cliente conectado desde {peer}")

    bytes_in = 0      
    bytes_out = 0    
    last_log = time.monotonic()

    # Levanta sesión con el agente (SDK Realtime)
    voice = SilverAIVoice()
    session = await voice.start()

    async with session:
        async def pump_agent_to_asterisk():
            """Saca audio TTS del agente y lo envía a Asterisk por AudioSocket."""
            nonlocal bytes_out, last_log
            try:
                async for pcm in session.stream_agent_tts():
                    if not pcm:
                        continue
                    # Protocolo audiosocket: 2 bytes (big-endian) = longitud, luego payload PCM16
                    writer.write(struct.pack("!H", len(pcm)) + pcm)
                    await writer.drain()
                    bytes_out += 2 + len(pcm)
                    now = time.monotonic()
                    if now - last_log >= 1.0:
                        print(f"[Bridge] IN={bytes_in}  OUT={bytes_out}  (último ~1s)")
                        bytes_in = 0
                        bytes_out = 0
                        last_log = now
            except asyncio.CancelledError:
                # cierre normal
                pass

        # *** Importante: lanzar la tarea de salida en paralelo ***
        pump_task = asyncio.create_task(pump_agent_to_asterisk())

        try:
            while True:
                # Lee frames del AudioSocket (2 bytes de tamaño + payload PCM16)
                try:
                    hdr = await reader.readexactly(2)
                    (size,) = struct.unpack("!H", hdr)
                    if size == 0:
                        continue
                    data = await reader.readexactly(size)
                except asyncio.IncompleteReadError:
                    # Fallback “crudo”: leer 320 bytes (~20ms a 8k) si el peer no mandó header
                    data = await reader.readexactly(320)

                # Entrega audio entrante al agente
                session.feed_pcm16(data)

                bytes_in += 2 + len(data)  # header+payload para tener simetría con OUT
                now = time.monotonic()
                if now - last_log >= 1.0:
                    print(f"[Bridge] IN={bytes_in}  OUT={bytes_out}  (último ~1s)")
                    bytes_in = 0
                    bytes_out = 0
                    last_log = now

        except (asyncio.IncompleteReadError, ConnectionResetError):
            # El peer colgó o se cortó
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
