from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
import asyncio
import json

router = APIRouter()

@router.websocket("/ws/v1/demo")
async def websocket_demo(websocket: WebSocket):
    await websocket.accept()
    logger.info("Demo WebSocket connected")
    
    try:
        # Send initial "ready" message or similar if protocol requires
        # Based on AIAssistantPanel.tsx:
        # if (data.type === 'session_ready' || (data.type === 'state_update' && data.state === 'listening'))
        
        await websocket.send_json({
            "type": "session_ready",
            "session_id": "demo-session-local",
            "audio_format": "pcm_s16le",
            "sample_rate": 24000
        })
        
        while True:
            data = await websocket.receive()
            
            if "bytes" in data:
                # Echo audio back or process (for now, just log and discard to avoid feedback loop if not handling properly)
                # Ensure we don't block
                pass
                
            elif "text" in data:
                try:
                    msg = json.loads(data["text"])
                    if msg.get("action") == "start_session":
                         await websocket.send_json({
                            "type": "state_update",
                            "state": "listening"
                        })
                    logger.debug(f"Received text: {msg}")
                except:
                    pass
                    
    except WebSocketDisconnect:
        logger.info("Demo WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
