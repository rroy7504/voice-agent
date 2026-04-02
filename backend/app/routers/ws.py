"""WebSocket endpoints for dashboard observation and customer call audio."""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.event_bus import event_bus
from app.core.call_store import call_store
from app.services.voice_agent import VoiceAgent

router = APIRouter()


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    """Agent observation dashboard — read-only event stream."""
    await websocket.accept()
    queue = event_bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)


@router.websocket("/ws/call")
async def call_ws(websocket: WebSocket):
    """Customer call — bidirectional audio + events."""
    await websocket.accept()

    audio_out_queue: asyncio.Queue = asyncio.Queue()

    async def text_out_callback(event_type: str, payload: dict):
        """Send JSON event to the customer browser."""
        try:
            await websocket.send_text(json.dumps({
                "event_type": event_type,
                "payload": payload,
            }))
        except Exception:
            pass

    agent = VoiceAgent(
        event_bus=event_bus,
        call_store=call_store,
        audio_out_queue=audio_out_queue,
        text_out_callback=text_out_callback,
    )

    # Start the Gemini session in the background
    agent_task = asyncio.create_task(agent.run())

    # Task to send Gemini audio responses back to browser
    async def send_audio_to_browser():
        try:
            while True:
                data = await audio_out_queue.get()
                try:
                    await websocket.send_bytes(data)
                except Exception as e:
                    print(f"Failed to send audio to browser: {e}")
                    break
        except asyncio.CancelledError:
            pass

    send_task = asyncio.create_task(send_audio_to_browser())

    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type", "")
            if msg_type == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"]:
                # Binary = PCM audio from browser mic
                await agent.feed_audio(message["bytes"])
            elif "text" in message and message["text"]:
                # JSON control message
                try:
                    msg = json.loads(message["text"])
                    if msg.get("type") == "end_call":
                        break
                    elif msg.get("type") == "text_message" and msg.get("text"):
                        user_text = msg["text"]
                        print(f"User text: {user_text}")
                        await agent.send_text(user_text)
                except json.JSONDecodeError:
                    pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await agent.stop()
        send_task.cancel()
        try:
            await agent_task
        except Exception:
            pass
