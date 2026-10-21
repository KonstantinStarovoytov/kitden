"""A tiny stdio MCP server for gateway tests.

    python echo_server.py NAME [--mark FILE] [--hang]

NAME is what `clash` answers, so two copies can be told apart. `--mark` writes FILE when the
process starts; `--hang` never answers, like a server stuck at start.
"""

import os
import sys
import time
from pathlib import Path

import anyio
from mcp.server.mcpserver import MCPServer


def main() -> None:
    args = sys.argv[1:]
    name = args[0] if args else "echo"
    if "--mark" in args:
        Path(args[args.index("--mark") + 1]).write_text(name)
    if "--hang" in args:
        time.sleep(3600)

    server = MCPServer(name)

    @server.tool(description="Answer with the text.")
    def echo(text: str) -> str:
        return text

    @server.tool(description="Wait, then answer. With `note`, write that file when waiting starts.")
    async def slow(seconds: float = 30, note: str = "") -> str:
        if note:
            Path(note).write_text("waiting")
        await anyio.sleep(seconds)
        return "done"

    @server.tool(description="Say which server answers.")
    def clash() -> str:
        return name

    @server.tool(description="Where the server runs: folder, arguments and env names.")
    def where() -> dict:
        return {
            "cwd": os.getcwd(),
            "args": args,
            "home": os.environ.get("HOME"),
            "path": os.environ.get("PATH"),
            "env": sorted(os.environ),
        }

    server.run()


if __name__ == "__main__":
    main()
