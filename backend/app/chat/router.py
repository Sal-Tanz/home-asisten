"""Socket.IO router for voice chat pipeline (STT -> AI -> TTS)."""

import asyncio
import json
import logging
import base64
from typing import Dict
import socketio

from app.chat.models import ChatSession
from app.chat.tools import TOOLS, SYSTEM_PROMPT
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
    """Handle incoming audio data and orchestrate STT -> AI -> TTS pipeline."""
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

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.get_messages_as_openai_format()

        response_text = ""

        async def on_text_chunk(chunk: str):
            """Handle streaming text chunks from AI."""
            nonlocal response_text
            response_text += chunk
            await sio.emit('text_chunk', {'text': chunk}, to=sid)

        async def on_tool_call(tool_call: dict):
            """Handle tool execution requests from AI."""
            tool_name = tool_call['name']

            args = tool_call['args']
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            logger.info(f"Tool call: {tool_name} with args: {args}")

            if tool_name == 'list_devices':
                return await _list_devices()

            elif tool_name == 'get_device_status':
                return await _get_device_status(args.get('device_id', ''))

            elif tool_name == 'control_device':
                return await _control_device(
                    device_id=args.get('device_id', ''),
                    action=args.get('action', ''),
                )

            return {"error": f"Unknown tool: {tool_name}"}

        # Stream AI response with tool support
        await ai_agent.stream_with_tools(messages, TOOLS, on_text_chunk, on_tool_call)

        # Step 3: Text-to-Speech (if we have response text)
        if response_text:
            session.add_message('assistant', response_text)
            await sio.emit('response', {'text': response_text}, to=sid)

            await sio.emit('status', {'state': 'speaking'}, to=sid)

            # Stream TTS clause-by-clause for lower latency
            clauses = tts_service.split_into_clauses(response_text)
            for clause in clauses:
                await tts_service.synthesize_stream(clause, lambda chunk: sio.emit(
                    'audio_chunk', {'audio': base64.b64encode(chunk).decode()}, to=sid
                ))

            await sio.emit('audio_done', {}, to=sid)

        # Return to listening state
        await sio.emit('status', {'state': 'listening'}, to=sid)

    except Exception as e:
        logger.error(f"Error in audio_data handler: {e}", exc_info=True)
        await sio.emit('error', {'message': str(e)}, to=sid)
        await sio.emit('status', {'state': 'listening'}, to=sid)


@sio.event
async def text_message(sid, data):
    """Handle text input — same pipeline as audio_data but skip STT."""
    session = sessions.get(sid)
    if not session:
        logger.warning(f"No session found for {sid}")
        return

    try:
        transcript = data.get('text', '').strip()
        if not transcript:
            await sio.emit('error', {'message': 'Pesan kosong'}, to=sid)
            return

        logger.info(f"Text message: {transcript}")
        await sio.emit('transcript', {'text': transcript}, to=sid)
        session.add_message('user', transcript)

        # AI Agent processing with tools
        await sio.emit('status', {'state': 'thinking'}, to=sid)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.get_messages_as_openai_format()

        response_text = ""

        async def on_text_chunk(chunk: str):
            nonlocal response_text
            response_text += chunk
            await sio.emit('text_chunk', {'text': chunk}, to=sid)

        async def on_tool_call(tool_call: dict):
            tool_name = tool_call['name']
            args = tool_call['args']
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            logger.info(f"Tool call: {tool_name} with args: {args}")

            if tool_name == 'list_devices':
                return await _list_devices()
            elif tool_name == 'get_device_status':
                return await _get_device_status(args.get('device_id', ''))
            elif tool_name == 'control_device':
                return await _control_device(
                    device_id=args.get('device_id', ''),
                    action=args.get('action', ''),
                )
            return {"error": f"Unknown tool: {tool_name}"}

        await ai_agent.stream_with_tools(messages, TOOLS, on_text_chunk, on_tool_call)

        if response_text:
            session.add_message('assistant', response_text)
            await sio.emit('response', {'text': response_text}, to=sid)
            await sio.emit('status', {'state': 'speaking'}, to=sid)

            clauses = tts_service.split_into_clauses(response_text)
            for clause in clauses:
                await tts_service.synthesize_stream(clause, lambda chunk: sio.emit(
                    'audio_chunk', {'audio': base64.b64encode(chunk).decode()}, to=sid
                ))
            await sio.emit('audio_done', {}, to=sid)

        await sio.emit('status', {'state': 'listening'}, to=sid)

    except Exception as e:
        logger.error(f"Error in text_message handler: {e}", exc_info=True)
        await sio.emit('error', {'message': str(e)}, to=sid)
        await sio.emit('status', {'state': 'listening'}, to=sid)


# --- Tool execution helpers ---

async def _list_devices():
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


async def _get_device_status(device_id: str):
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import get_device

    async with AsyncSessionLocal() as db:
        device = await get_device(db, device_id)

    if device:
        return {
            "device_id": device.device_id,
            "name": device.name,
            "state": json.loads(device.state)
        }
    return {"error": "Device not found"}


async def _control_device(device_id: str, action: str):
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import get_device, update_device_state, create_action_log

    # Single DB session for entire TOGGLE operation
    async with AsyncSessionLocal() as db:
        device = await get_device(db, device_id)
        if not device:
            return {"error": "Device not found"}

        state = json.loads(device.state)

        if action == 'TOGGLE':
            current = state.get("relay_1", "OFF")
            action = "OFF" if current == "ON" else "ON"

        state["relay_1"] = action
        await update_device_state(db, device_id, state)
        await create_action_log(db, device_id, "relay_1", action, "voice")

        logger.info(f"Device {device_id} relay_1 set to {action}")
        return {"success": True, "device_id": device_id, "action": action}