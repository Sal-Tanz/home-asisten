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
session_locks: Dict[str, asyncio.Lock] = {}  # Per-session processing locks

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
    session_locks.pop(sid, None)  # Cleanup lock
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def audio_data(sid, data):
    """Handle incoming audio data and orchestrate STT -> AI -> TTS pipeline.

    Accepts audio either as a raw binary ArrayBuffer (sent by the VAD frontend,
    received here as `bytes`) or as a legacy ``{audio: <base64>}`` dict.
    """
    session = sessions.get(sid)
    if not session:
        logger.warning(f"No session found for {sid}")
        return

    # Session lock to prevent concurrent processing. With VAD segmentation
    # audio arrives as whole utterances, so a busy lock just means a segment
    # came in while the AI was still responding — drop it silently.
    if sid not in session_locks:
        session_locks[sid] = asyncio.Lock()

    lock = session_locks[sid]

    if lock.locked():
        logger.info(f"Session {sid} busy, dropping audio segment")
        return

    async with lock:
        try:
            # Normalize payload to raw bytes. Frontend sends an ArrayBuffer
            # (arrives as `bytes`); keep base64/dict fallback for compatibility.
            if isinstance(data, (bytes, bytearray)):
                audio_bytes = bytes(data)
            elif isinstance(data, dict) and 'audio' in data:
                audio_b64 = data['audio']
                if not isinstance(audio_b64, str):
                    await sio.emit('error', {'message': 'Invalid audio data type'}, to=sid)
                    return
                # Strip data URL prefix if present
                if audio_b64.startswith('data:') and ',' in audio_b64:
                    audio_b64 = audio_b64.split(',')[1]
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await sio.emit('error', {'message': 'Audio decode failed'}, to=sid)
                    return
            else:
                await sio.emit('error', {'message': 'Invalid audio data'}, to=sid)
                return

            # Validate audio size
            if len(audio_bytes) < 100:
                logger.info(f"Audio too small: {len(audio_bytes)} bytes")
                return

            # Validate audio format (check WebM header)
            webm_header = bytes([0x1A, 0x45, 0xDF, 0xA3])
            if audio_bytes[:4] != webm_header:
                logger.warning(f"Invalid WebM header: {audio_bytes[:4].hex()}")
                await sio.emit('status', {'state': 'listening'}, to=sid)
                return

            # Step 1: Speech-to-Text
            await sio.emit('status', {'state': 'transcribing'}, to=sid)
            result = await stt_service.transcribe(audio_bytes, audio_format='webm')

            if result['error'] or not result['transcript']:
                # `error` may be present but None (API success, no speech),
                # so use `or` to fall back instead of .get()'s missing-key default.
                error_msg = result.get('error') or 'Tidak ada suara terdeteksi'

                if 'ffmpeg' in error_msg.lower():
                    user_error = 'Audio conversion failed. Please try speaking again.'
                elif 'google' in error_msg.lower() or 'api' in error_msg.lower():
                    user_error = 'Speech recognition service unavailable. Please try again later.'
                else:
                    user_error = 'No speech detected. Please speak louder and closer to the microphone.'

                await sio.emit('error', {'message': user_error}, to=sid)
                await sio.emit('status', {'state': 'listening'}, to=sid)
                return

            transcript = result['transcript']
            logger.info(f"Transcribed ({sid}): {transcript}")
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
                        relay=args.get('relay', 'relay_1'),
                        sid=sid,
                    )

                return {"error": f"Unknown tool: {tool_name}"}

            # Stream AI response with tool support
            await ai_agent.stream_with_tools(messages, TOOLS, on_text_chunk, on_tool_call)

            # Step 3: Text-to-Speech (if we have response text)
            if response_text:
                session.add_message('assistant', response_text)

                await sio.emit('status', {'state': 'speaking'}, to=sid)

                # Synthesize each clause to a complete MP3 blob, then emit it
                # as a single audio_chunk. Each chunk is a self-contained MP3
                # so the browser can decode it reliably (no broken fragments).
                clauses = tts_service.split_into_clauses(response_text)
                for clause in clauses:
                    audio_bytes = await tts_service.synthesize_to_bytes(clause)
                    if audio_bytes:
                        await sio.emit('audio_chunk', {
                            'audio': base64.b64encode(audio_bytes).decode()
                        }, to=sid)

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

    # Get or create lock for this session
    if sid not in session_locks:
        session_locks[sid] = asyncio.Lock()

    lock = session_locks[sid]

    # Wait for lock (blocking) — text messages should always be processed
    async with lock:
        try:
            transcript = data.get('text', '').strip()
            if not transcript:
                await sio.emit('error', {'message': 'Pesan kosong'}, to=sid)
                return

            logger.info(f"Text message ({sid}): {transcript}")
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
                        relay=args.get('relay', 'relay_1'),
                        sid=sid,
                    )
                return {"error": f"Unknown tool: {tool_name}"}

            await ai_agent.stream_with_tools(messages, TOOLS, on_text_chunk, on_tool_call)

            if response_text:
                session.add_message('assistant', response_text)
                await sio.emit('status', {'state': 'speaking'}, to=sid)

                clauses = tts_service.split_into_clauses(response_text)
                for clause in clauses:
                    audio_bytes = await tts_service.synthesize_to_bytes(clause)
                    if audio_bytes:
                        await sio.emit('audio_chunk', {
                            'audio': base64.b64encode(audio_bytes).decode()
                        }, to=sid)
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
            state = json.loads(d.state) if d.state else {}
            relay_names = _safe_parse_relay_names(d.relay_names)
            devices.append({
                "device_id": d.device_id,
                "name": d.name,
                "room": d.room,
                "type": d.type,
                "relay_count": d.relay_count,
                "relay_names": relay_names,
                "relays": _describe_relays(relay_names, state),
                "state": state,
            })
    return {"devices": devices}


def _safe_parse_state(state_str: str) -> dict:
    """Safely parse device state JSON, returns empty dict on error."""
    try:
        return json.loads(state_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _safe_parse_relay_names(relay_names_str: str) -> dict:
    """Safely parse relay_names JSON, returns empty dict on error/empty."""
    try:
        return json.loads(relay_names_str) if relay_names_str else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _describe_relays(relay_names: dict, state: dict) -> list:
    """Build a human-readable list of relays with custom name and current state.

    Each item: {"name": "Kipas", "key": "relay_1", "state": "OFF"}.
    Lets the AI refer to the custom name (e.g. "Kipas") instead of the raw
    "relay_1" key when speaking to the user. Falls back to "Relay {idx}"
    only when no custom name is set.
    """
    relay_names = relay_names or {}
    state = state or {}
    described = []
    for key in sorted(relay_names.keys()):
        idx = key.split("_")[-1] if "_" in key else key
        name = relay_names.get(key) or f"Relay {idx}"
        described.append({"name": name, "key": key, "state": state.get(key, "OFF")})
    return described


async def _get_device_status(device_id: str):
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import get_device

    async with AsyncSessionLocal() as db:
        device = await get_device(db, device_id)

    if device:
        state = _safe_parse_state(device.state)
        relay_names = _safe_parse_relay_names(device.relay_names)
        return {
            "device_id": device.device_id,
            "name": device.name,
            "room": device.room,
            "relay_names": relay_names,
            "relays": _describe_relays(relay_names, state),
            "state": state,
        }
    return {"error": "Device not found"}


async def _control_device(device_id: str, action: str, relay: str = "relay_1", sid: str = None):
    from app.db.database import AsyncSessionLocal
    from app.devices.crud import get_device, update_device_state, create_action_log

    # Single DB session for the whole operation
    async with AsyncSessionLocal() as db:
        device = await get_device(db, device_id)
        if not device:
            return {"error": "Device not found"}

        state = _safe_parse_state(device.state)

        if action == 'TOGGLE':
            current = state.get(relay, "OFF")
            action = "OFF" if current == "ON" else "ON"

        state[relay] = action
        await update_device_state(db, device_id, state)
        await create_action_log(db, device_id, relay, action, "voice")

        # Publish the command to the physical device via MQTT so it actually
        # changes state (lazy import avoids a circular import with app.main).
        try:
            from app.main import mqtt_service
            if mqtt_service and mqtt_service.is_connected():
                await mqtt_service.publish_command(
                    device_id=device_id, relay=relay, action=action
                )
            else:
                logger.warning(f"MQTT not connected; {device_id} {relay} updated in DB only")
        except Exception as e:
            logger.error(f"MQTT publish failed for {device_id}: {e}")

        # Notify the frontend so the device panel refreshes in real time.
        # Targeted to the controlling session to avoid unnecessary refreshes
        # on other clients.
        if sid:
            await sio.emit('device_update', {
                "device_id": device_id,
                "relay": relay,
                "action": action,
            }, to=sid)

        logger.info(f"Device {device_id} {relay} set to {action}")
        relay_names = _safe_parse_relay_names(device.relay_names)
        idx = relay.split("_")[-1] if "_" in relay else relay
        relay_name = relay_names.get(relay) or f"Relay {idx}"
        return {
            "success": True,
            "device_id": device_id,
            "name": device.name,
            "room": device.room,
            "relay": relay,
            "relay_name": relay_name,
            "action": action,
        }