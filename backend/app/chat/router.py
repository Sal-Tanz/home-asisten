"""Socket.IO router for voice chat pipeline (STT → AI → TTS)."""

import asyncio
import json
import logging
import base64
from typing import Dict
import socketio

from app.chat.models import ChatSession
from app.chat.tools import TOOLS
from app.core.stt_service import STTService
from app.core.tts_service import TTSService
from app.core.ai_agent import AIAgent

logger = logging.getLogger(__name__)

# Initialize services
stt_service = STTService()
tts_service = TTSService()
ai_agent = AIAgent()

# Session storage
sessions: Dict[str, ChatSession] = {}

# Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio)


@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    sessions[sid] = ChatSession(session_id=sid)
    logger.info(f"Client connected: {sid}")
    await sio.emit('connected', {'session_id': sid}, to=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    sessions.pop(sid, None)
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def audio_data(sid, data):
    """Handle incoming audio data and orchestrate STT → AI → TTS pipeline."""
    session = sessions.get(sid)
    if not session:
        logger.warning(f"No session found for {sid}")
        return

    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(data['audio'])

        # Step 1: Speech-to-Text
        await sio.emit('status', {'state': 'transcribing'}, to=sid)
        result = await stt_service.transcribe(audio_bytes, audio_format='webm')

        if result['error'] or not result['transcript']:
            error_msg = result.get('error', 'Tidak ada suara terdeteksi')
            await sio.emit('error', {'message': error_msg}, to=sid)
            await sio.emit('status', {'state': 'listening'}, to=sid)
            return

        transcript = result['transcript']
        logger.info(f"Transcribed: {transcript}")
        await sio.emit('transcript', {'text': transcript}, to=sid)
        session.add_message('user', transcript)

        # Step 2: AI Agent processing with tools
        await sio.emit('status', {'state': 'thinking'}, to=sid)

        # Prepare messages with system prompt
        system_msg = {
            "role": "system",
            "content": (
                "Kamu adalah ElBot, asisten rumah pintar berbahasa Indonesia. "
                "Kamu ramah, helpful, dan efisien. Selalu jawab dalam Bahasa Indonesia. "
                "Untuk perintah kontrol perangkat, gunakan tools yang tersedia. "
                "Jawaban harus singkat dan jelas (1-2 kalimat)."
            ),
        }
        messages = [system_msg] + session.get_messages_as_openai_format()

        response_text = ""

        async def on_text_chunk(chunk: str):
            """Handle streaming text chunks from AI."""
            nonlocal response_text
            response_text += chunk
            await sio.emit('text_chunk', {'text': chunk}, to=sid)

        async def on_tool_call(tool_call: dict):
            """Handle tool execution requests from AI."""
            tool_name = tool_call['name']

            # Parse args if still string
            args = tool_call['args']
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            logger.info(f"Tool call: {tool_name} with args: {args}")

            # Execute tool
            if tool_name == 'list_devices':
                from app.db.database import AsyncSessionLocal
                from app.devices.models import Device
                from sqlalchemy import select

                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Device).limit(100))
                    devices = []
                    for d in result.scalars().all():
                        devices.append({
                            "device_id": d.device_id,
                            "name": d.name,
                            "room": d.room,
                            "state": json.loads(d.state) if d.state else {}
                        })
                return {"devices": devices}

            elif tool_name == 'get_device_status':
                from app.db.database import AsyncSessionLocal
                from app.devices.crud import get_device

                async with AsyncSessionLocal() as db:
                    device = await get_device(db, args['device_id'])

                if device:
                    return {
                        "device_id": device.device_id,
                        "name": device.name,
                        "state": json.loads(device.state)
                    }
                return {"error": "Device not found"}

            elif tool_name == 'control_device':
                from app.db.database import AsyncSessionLocal
                from app.devices.crud import get_device, update_device_state, create_action_log

                device_id = args['device_id']
                action = args['action']

                # Handle TOGGLE action
                if action == 'TOGGLE':
                    async with AsyncSessionLocal() as db:
                        device = await get_device(db, device_id)
                        if device:
                            state = json.loads(device.state)
                            current = state.get("relay_1", "OFF")
                            action = "OFF" if current == "ON" else "ON"

                # Update device state and log action
                async with AsyncSessionLocal() as db:
                    device = await get_device(db, device_id)
                    if device:
                        state = json.loads(device.state)
                        state["relay_1"] = action
                        await update_device_state(db, device_id, state)
                        await create_action_log(db, device_id, "relay_1", action, "voice")
                        logger.info(f"Device {device_id} relay_1 set to {action}")
                        return {"success": True, "device_id": device_id, "action": action}

                return {"error": "Device not found"}

            return {"error": f"Unknown tool: {tool_name}"}

        # Stream AI response with tool support
        await ai_agent.stream_with_tools(messages, TOOLS, on_text_chunk, on_tool_call)

        # Step 3: Text-to-Speech (if we have response text)
        if response_text:
            session.add_message('assistant', response_text)
            await sio.emit('response', {'text': response_text}, to=sid)

            # Stream TTS audio
            await sio.emit('status', {'state': 'speaking'}, to=sid)

            async def emit_audio_chunk(chunk: bytes):
                """Emit audio chunk as hex string."""
                await sio.emit('audio_chunk', {'audio': chunk.hex()}, to=sid)

            await tts_service.synthesize_stream(response_text, emit_audio_chunk)
            await sio.emit('audio_done', {}, to=sid)

        # Return to listening state
        await sio.emit('status', {'state': 'listening'}, to=sid)

    except Exception as e:
        logger.error(f"Error in audio_data handler: {e}", exc_info=True)
        await sio.emit('error', {'message': str(e)}, to=sid)
        await sio.emit('status', {'state': 'listening'}, to=sid)
