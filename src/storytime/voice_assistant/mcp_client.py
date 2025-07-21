"""Async MCP client for voice assistant integration."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class MCPClient:
    """Simple client for Storytime's HTTP MCP server using SSE."""

    def __init__(self, base_url: str, access_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=None)
        self._sse_task: asyncio.Task | None = None
        self._message_endpoint: str | None = None
        self._message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._request_id = 0
        self._response = None

    async def connect(self) -> None:
        """Connect to the SSE endpoint and start listening."""

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Start streaming request
        self._response = self._client.stream("GET", "/mcp-server/sse", headers=headers)
        response = await self._response.__aenter__()
        response.raise_for_status()

        async def _listen() -> None:
            try:
                current_event = None
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                        if not data:
                            continue

                        if current_event == "endpoint":
                            # This is the endpoint URL for POST requests
                            self._message_endpoint = data
                        elif current_event == "message":
                            # This is a JSON-RPC message
                            try:
                                payload = json.loads(data)
                                await self._message_queue.put(payload)
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                print(f"SSE listening error: {e}")

        self._sse_task = asyncio.create_task(_listen())

        # Wait for the endpoint message to be set
        for _ in range(50):  # Wait up to 5 seconds
            if self._message_endpoint:
                break
            await asyncio.sleep(0.1)

        if not self._message_endpoint:
            raise RuntimeError("Timeout waiting for MCP endpoint")

    async def disconnect(self) -> None:
        """Close the SSE connection and HTTP client."""
        if self._sse_task:
            self._sse_task.cancel()
            with contextlib.suppress(Exception):
                await self._sse_task
        if self._response:
            await self._response.__aexit__(None, None, None)
        await self._client.aclose()

    async def iter_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Yield messages received from the server."""
        while True:
            message = await self._message_queue.get()
            yield message

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> None:
        """Send a tools/call request over MCP."""
        if not self._message_endpoint:
            raise RuntimeError("Client not connected")

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        await self._client.post(self._message_endpoint, json=payload, headers=headers)
