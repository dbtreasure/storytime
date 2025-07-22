#!/usr/bin/env python3
"""Test WebSocket binding with IPv4 patching."""

# CRITICAL: Force IPv4-only resolution before importing websockets
import socket

_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host in ('localhost', '::1', ''):
        host = '127.0.0.1'
        family = socket.AF_INET  # Force IPv4
    return _original_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = _ipv4_only_getaddrinfo

import asyncio
import logging

import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_server():
    """Test basic WebSocket server binding."""

    async def handler(websocket, path):
        logger.info(f"Client connected from {websocket.remote_address}")
        await websocket.send("Hello from test server!")
        await websocket.close()

    # Test different host configurations
    hosts_to_test = [
        ("127.0.0.1", 8766, "IPv4 localhost"),
        ("0.0.0.0", 8767, "IPv4 all interfaces"),
    ]

    for host, port, desc in hosts_to_test:
        try:
            logger.info(f"\nTesting {desc}: {host}:{port}")
            server = await websockets.serve(handler, host, port)
            logger.info(f"✓ Successfully bound to {host}:{port}")

            # Get actual bound address
            for sock in server.sockets:
                logger.info(f"  Socket info: {sock.getsockname()}")

            await server.close()
            await server.wait_closed()

        except Exception as e:
            logger.error(f"✗ Failed to bind to {host}:{port}: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_server())
