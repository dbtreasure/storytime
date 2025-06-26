# Voice Assistant Integration Guide

This document explains how to connect a voice assistant (such as ChatGPT's Realtime API) to the Storytime MCP server. The MCP server exposes the `/knowledge` search endpoints as JSON‑RPC tools that can be called during a conversation to retrieve audiobook content.

## 1. Register a Client via OAuth

The MCP server uses OAuth 2.1 with PKCE for authentication. Clients must register dynamically before requesting authorization codes.

Example registration request:

```bash
curl -X POST http://localhost:8000/api/v1/mcp-oauth/register \
  -H 'Content-Type: application/json' \
  -d '{
    "client_name": "ChatGPT Voice Assistant",
    "redirect_uris": ["http://localhost:8000/callback"],
    "grant_types": ["authorization_code"],
    "response_types": ["code"]
  }'
```

The server will return a `client_id` and `client_secret` to use in the authorization flow.

## 2. Obtain an Access Token

After registration the client should follow the standard OAuth authorization code flow with PKCE to obtain a JWT access token. Supply this token as a `Bearer` header when connecting to the MCP server.

## 3. Communicating with the MCP Server

Use Server‑Sent Events (SSE) for real‑time communication. The following Python snippet demonstrates connecting and invoking a tool using the `MCPClient` helper:

```python
import asyncio
from storytime.voice_assistant.mcp_client import MCPClient

async def main():
    client = MCPClient(base_url="http://localhost:8000", access_token="YOUR_JWT")
    await client.connect()

    # Call the search_library tool
    await client.call_tool("search_library", {"query": "luck"})

    async for message in client.iter_messages():
        print(message)

asyncio.run(main())
```

The first SSE message contains the endpoint to POST JSON‑RPC requests. Subsequent messages contain tool responses formatted for the OpenAI Realtime API.

---

This guide provides the basics needed to start integrating a voice assistant. Refer to the MCP server implementation under `src/storytime/mcp` for full details of the available tools and parameters.
