# mcp_handler.py
from agents.mcp.server import MCPServerSse

# Lista de configuraciones de MCPs que quieras usar
MCP_CONFIG = [
    {
        "name": "ticket_mcp_server",
        "url": "http://localhost:8585/mcp"
    },
    # Agrega más diccionarios aquí para nuevos MCPs
]

# Función que inicializa y conecta todos los MCP servers
async def init_mcp_servers():
    servers = []

    for cfg in MCP_CONFIG:
        server = MCPServerSse(
            params={
                "url": cfg["url"],
                "timeout": 5,
                "sse_read_timeout": 300,
            },
            cache_tools_list=True,
            name=cfg["name"]
        )
        await server.connect()
        print(f"✅ Conectado a MCP: {cfg['url']}")
        servers.append(server)

    return servers
