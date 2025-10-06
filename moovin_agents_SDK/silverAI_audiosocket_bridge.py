# Puente AudioSocket (TCP) <-> SilverAIVoiceSession (PCM16 mono 8k)
import asyncio, struct
from SilverAI_Voice import SilverAIVoice
from dotenv import load_dotenv
load_dotenv() 

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    voice = SilverAIVoice()
    session = await voice.start()  # abre runner + session realtime
    async with session:
        async def pump_agent_to_asterisk():
            async for pcm in session.stream_agent_tts():
                if not pcm:
                    continue
                writer.write(struct.pack("!H", len(pcm)) + pcm)
                await writer.drain()

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
