"""Entry point for running the MCP server as a module."""

import asyncio
import logging

from .server import start_mcp_server

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        asyncio.run(start_mcp_server())
    except KeyboardInterrupt:
        print("\nMCP server shutdown gracefully")
    except Exception as e:
        print(f"Error starting MCP server: {e}")
        raise
