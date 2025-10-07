# Puente AudioSocket (TCP) <-> SilverAIVoiceSession (PCM16 mono 8k)
import asyncio, struct, time
from SilverAI_Voice import SilverAIVoice
from dotenv import load_dotenv
load_dotenv() 

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    print("[AudioSocket Bridge] cliente conectado")
    peer = writer.get_extra_info("peername") or ("?", 0)
    print(f"[AudioSocket Bridge] cliente conectado desde {peer}")
    bytes_in = 0     # Asterisk -> Bridge
    bytes_out = 0    # Bridge -> Asterisk
    last_log = time.monotonic()
    voice = SilverAIVoice()
    session = await voice.start()  # abre runner + session realtime
    async with session:
        async def pump_agent_to_asterisk():
            nonlocal bytes_out, last_log
            async for pcm in session.stream_agent_tts():
                if not pcm:
                    continue
                writer.write(struct.pack("!H", len(pcm)) + pcm)
                await writer.drain()
                bytes_out += 2 + len(pcm)  # 2 bytes de header + payload
                now = time.monotonic()
                if now - last_log >= 1.0:
                    print(f"[Bridge] IN={bytes_in}  OUT={bytes_out}  (último ~1s)")
                    bytes_in = 0
                    bytes_out = 0
                    last_log = now

        pump_task = asyncio.create_task(pump_agent_to_asterisk())
        try:
            while True:
                try:
                    hdr = await reader.readexactly(2)
                    (size,) = struct.unpack("!H", hdr)
                    if size == 0:
                        continue
                    data = await reader.readexactly(size)
                except asyncio.IncompleteReadError:
                    data = await reader.readexactly(320)
                session.feed_pcm16(data)
                bytes_in += 2 + len(data)  # 2 bytes de header + payload
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
    import os
    asyncio.run(main())
