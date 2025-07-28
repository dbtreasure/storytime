"""WebSocket proxy for voice assistant to work through main FastAPI server."""

import asyncio
import logging
from typing import Optional

import websockets
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from ..database import User
from .auth import get_current_user_websocket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/voice-assistant")
async def websocket_proxy(
    websocket: WebSocket,
    user: Optional[User] = Depends(get_current_user_websocket),
):
    """Proxy WebSocket connections to the internal voice assistant server."""
    if not user:
        await websocket.close(code=1008, reason="Unauthorized")
        return
        
    await websocket.accept()
    
    # Connect to internal WebSocket server on port 8765
    internal_ws_url = "ws://localhost:8765"
    
    try:
        async with websockets.connect(internal_ws_url) as internal_ws:
            logger.info(f"User {user.email} connected to voice assistant proxy")
            
            # Create tasks for bidirectional message forwarding
            async def forward_to_internal():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await internal_ws.send(data)
                except WebSocketDisconnect:
                    logger.info("Client disconnected")
                except Exception as e:
                    logger.error(f"Error forwarding to internal: {e}")
                    
            async def forward_to_client():
                try:
                    async for message in internal_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except ConnectionClosed:
                    logger.info("Internal WebSocket closed")
                except Exception as e:
                    logger.error(f"Error forwarding to client: {e}")
            
            # Run both forwarding tasks concurrently
            await asyncio.gather(
                forward_to_internal(),
                forward_to_client(),
                return_exceptions=True
            )
            
    except Exception as e:
        logger.error(f"WebSocket proxy error: {e}")
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        logger.info(f"User {user.email} disconnected from voice assistant proxy")