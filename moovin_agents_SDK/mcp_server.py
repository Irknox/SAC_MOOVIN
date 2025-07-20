import sys
import os
from agents.mcp.server import MCPServerStdio

def get_stdio_server():
    handler_path = os.path.join(os.path.dirname(__file__), "mcp_handler.py")
    python_executable = sys.executable  # Esto apunta al python del venv activo
    return MCPServerStdio(
        params={
            "command": python_executable,
            "args": [handler_path],
            "cwd": os.path.dirname(__file__),
        },
        name="Moovin MCP Stdio",
        cache_tools_list=True,
    )