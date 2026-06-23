"""
Web-based Voice AI Chat Application
Flask backend with WebSocket support for real-time communication
"""

from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import logging
import os
import time
import tempfile
import shutil
import threading
import secrets
import subprocess as _subprocess
import requests as _requests
from ai_client import AIClient
from agent_tools import AgentTools
from face_engine import FaceRecognitionEngine, background_face_scanner, camera_lock
import cv2
import uuid
from dotenv import load_dotenv
from orchestrator import AgentOrchestrator, OrchestratorConfig

# Persistent HTTP session for Google STT (connection pooling — avoids TCP+TLS handshake per request)
_stt_session = _requests.Session()
_stt_session.headers.update({
    'User-Agent': 'Mozilla/5.0',
    'Content-Type': 'audio/x-flac; rate=16000',
})
# Default Google Speech API key (same as speech_recognition library uses)
_GOOGLE_STT_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
_GOOGLE_STT_URL = "https://www.google.com/speech-api/v2/recognize"

# Concurrent audio processing counter
_audio_processing_count = 0
_audio_processing_lock = threading.Lock()

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
CORS(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Initialize Face Recognition Engine
face_engine = FaceRecognitionEngine(db_path='known_faces.json')
scanner_stop_flag = threading.Event()
scanner_thread = None

logger.info("Face Recognition Engine initialized")

# Verify ffmpeg is available (required by pydub for audio conversion)
if not shutil.which('ffmpeg'):
    logger.error("ffmpeg not found in PATH — audio processing will fail. Install with: sudo apt install ffmpeg")

# Initialize AI Client + Agent Tools
ai_client = AIClient()
VISION_ENABLED = os.getenv('VISION_ENABLED', 'false').lower() == 'true'
logger.info(f"Vision/multimodal support: {'ENABLED' if VISION_ENABLED else 'DISABLED'}")
agent_tools = AgentTools()

# Initialize Multi-Agent Orchestrator
MULTI_AGENT_ENABLED = os.getenv('MULTI_AGENT_ENABLED', 'false').lower() == 'true'
orchestrator = None

if MULTI_AGENT_ENABLED:
    config = OrchestratorConfig()
    orchestrator = AgentOrchestrator(ai_client, agent_tools, socketio, config)
    logger.info(f"Multi-agent orchestrator initialized with {len(orchestrator.agents)} agents")
    logger.info(f"Available agents: {list(orchestrator.agents.keys())}")
else:
    logger.info("Multi-agent mode DISABLED - using single-agent mode")

# Store conversation history per session
conversations = {}
conversations_last_active = {}
CONVERSATION_TTL = 3600  # 1 hour
MAX_HISTORY_SIZE = 12  # Keep system context + ~8 recent messages for speed
conversations_lock = threading.Lock()  # Thread-safe access to conversations

# Stop flags for cancelling generation (protected by conversations_lock for thread-safe access)
stop_flags = set()


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files (PWA manifest, icons, service worker)"""
    return send_from_directory('static', filename)


@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Test AI API connection"""
    try:
        success, message = ai_client.test_connection()
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500



@app.route('/api/tts', methods=['POST'])
def tts():
    """Generate text-to-speech audio using Microsoft Edge TTS (fast, natural voice)"""
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        os.makedirs('/home/elektro/ai-audio/static/audio', exist_ok=True)
        filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join('/home/elektro/ai-audio/static/audio', filename)

        # Clean old files (only files older than 5 minutes to avoid race conditions)
        now = time.time()
        audio_dir = '/home/elektro/ai-audio/static/audio'
        for f in os.listdir(audio_dir):
            if f.startswith('tts_'):
                fpath = os.path.join(audio_dir, f)
                try:
                    if now - os.path.getmtime(fpath) > 300:  # older than 5 minutes
                        os.remove(fpath)
                except OSError:
                    pass

        # Use edge-tts CLI subprocess to avoid gevent/asyncio event loop conflict
        import subprocess
        result = subprocess.run(
            [
                os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'edge-tts'),
                '--voice', 'id-ID-ArdiNeural',
                '--text', text,
                '--write-media', filepath,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"edge-tts failed: {result.stderr[:200]}")

        # Return base64 inline so frontend doesn't need a second fetch
        import base64
        with open(filepath, 'rb') as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
        return jsonify({'url': f'/static/audio/{filename}', 'base64': audio_b64})
    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/image/<filename>')
def serve_image(filename):
    """Serve captured camera images"""
    try:
        # Security: validate filename to prevent path traversal
        if '..' in filename or '/' in filename:
            return jsonify({'error': 'Invalid filename'}), 400

        filepath = os.path.join('/tmp', filename)

        if not os.path.exists(filepath):
            return jsonify({'error': 'Image not found'}), 404

        return send_from_directory('/tmp', filename, mimetype='image/jpeg')
    except Exception as e:
        logger.error(f"Image serve error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test-image-display')
def test_image_display():
    """Test endpoint to force emit tool_image event for debugging"""
    try:
        # Capture a test image
        result = agent_tools.execute('capture_camera', {'device': 0, 'description': 'Test image display'})
        result_data = json.loads(result)

        logger.info(f"Test image display: {result_data}")

        return jsonify({
            'success': True,
            'message': 'Test image captured. Check browser console for tool_image event.',
            'image_data': result_data
        })
    except Exception as e:
        logger.error(f"Test image display error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Global lock for face context state (prevents race condition in multi-greenlet environment)
_face_context_lock = threading.Lock()


@app.route('/api/register_face', methods=['POST'])
def register_face():
    """Admin endpoint untuk mendaftarkan wajah baru"""
    data = request.json
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'success': False, 'message': 'Nama harus diisi'})

    # Capture 5 foto dari kamera (with camera_lock to prevent conflicts)
    images = []
    with camera_lock:
        cap = cv2.VideoCapture(0)
        try:
            if not cap.isOpened():
                return jsonify({'success': False, 'message': 'Kamera tidak tersedia'})

            # Allow camera to warm up
            time.sleep(0.5)

            for i in range(5):
                ret, frame = cap.read()
                if ret:
                    images.append(frame)
                time.sleep(0.3)  # Jeda untuk variasi pose
        finally:
            # Always release camera, even if exception occurs
            cap.release()

    if len(images) < 3:
        return jsonify({'success': False, 'message': f'Gagal capture gambar (hanya {len(images)} foto)'})

    # Register ke engine
    result = face_engine.register_face(name, images)
    return jsonify(result)


@app.route('/api/list_faces', methods=['GET'])
def list_faces():
    """List semua wajah yang terdaftar"""
    try:
        registered = face_engine.list_registered()
        return jsonify({
            'success': True,
            'faces': registered,
            'total': len(registered)
        })
    except Exception as e:
        logger.error(f"List faces error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    """Handle client connection — inject AI instructions + persistent memory"""
    from memory import load_memory, load_instructions

    session_id = request.sid
    with conversations_lock:
        conversations[session_id] = []
        conversations_last_active[session_id] = time.time()

    _cleanup_stale_sessions()

    # Load AI instructions (technical guidance - static)
    instructions = load_instructions()
    if instructions:
        conversations[session_id].append({
            'role': 'user',
            'content': (
                '[INSTRUKSI AI - panduan teknis dan kapabilitas kamu. '
                'Ikuti instruksi ini untuk memberikan respons yang tepat dan sesuai]:\n\n'
                + instructions
            )
        })
        conversations[session_id].append({
            'role': 'assistant',
            'content': 'Baik, saya memahami kapabilitas dan instruksi saya.'
        })
        logger.info(f"Loaded instructions ({len(instructions)} chars) for {session_id}")

    # Load personal memory (user personality/context - dynamic)
    memory = load_memory()
    if memory:
        conversations[session_id].append({
            'role': 'user',
            'content': (
                '[MEMORI PERSONAL - ini adalah informasi yang kamu ingat '
                'tentang user ini. Gunakan untuk memberikan respons yang lebih personal, '
                'relevan, dan kontekstual tanpa perlu menyebutkan bahwa kamu membacanya dari file]:\n\n'
                + memory
            )
        })
        conversations[session_id].append({
            'role': 'assistant',
            'content': 'Baik, saya mengingat konteks personal user ini.'
        })
        logger.info(f"Loaded memory ({len(memory)} chars) for {session_id}")
    else:
        logger.info(f"No existing memory for {session_id}")

    emit('connected', {'session_id': session_id})


def _cleanup_stale_sessions():
    """Remove conversation data for sessions inactive longer than TTL"""
    now = time.time()
    with conversations_lock:
        stale = [sid for sid, ts in conversations_last_active.items()
                 if now - ts > CONVERSATION_TTL]
        for sid in stale:
            conversations.pop(sid, None)
            conversations_last_active.pop(sid, None)
            stop_flags.discard(sid)
            logger.info(f"Cleaned up stale session: {sid}")

    # Clean face context state outside main lock (uses separate lock)
    if stale and hasattr(handle_message, '_face_context_state'):
        with _face_context_lock:
            for sid in stale:
                handle_message._face_context_state.pop(sid, None)

    return stale


def _start_cleanup_timer():
    """Run _cleanup_stale_sessions every 5 minutes in background"""
    _cleanup_stale_sessions()
    timer = threading.Timer(300, _start_cleanup_timer)
    timer.daemon = True
    timer.start()


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    session_id = request.sid
    with conversations_lock:
        conversations.pop(session_id, None)
        conversations_last_active.pop(session_id, None)
    logger.info(f"Client disconnected: {session_id}")


@socketio.on('send_message')
def handle_message(data):
    """
    Handle incoming message from client with tool-use agent loop
    Args:
        data: {'message': str, 'language': str}
    """
    session_id = request.sid
    message = data.get('message', '')

    if not message:
        emit('error', {'message': 'Empty message'})
        return

    logger.info(f"Received message from {session_id}: {message[:50]}...")

    with conversations_lock:
        if session_id not in conversations:
            conversations[session_id] = []

        # Remove any pending stop flag from previous run (thread-safe)
        stop_flags.discard(session_id)

        history = conversations[session_id]
        conversations_last_active[session_id] = time.time()

    # Inject face recognition context only when face changes (avoid history bloat)
    cached_person = face_engine.get_cached_person()

    # Get or create session state for face tracking (thread-safe with lock)
    with _face_context_lock:
        if not hasattr(handle_message, '_face_context_state'):
            handle_message._face_context_state = {}

        session_state = handle_message._face_context_state
        if session_id not in session_state:
            session_state[session_id] = {'last_face': None}

    # All history modifications protected by conversations_lock
    with conversations_lock:
        # Only inject if face changed
        if cached_person:
            with _face_context_lock:
                last_face = session_state[session_id]['last_face']
                if cached_person['name'] != last_face:
                    context_msg = (
                        f"[SYSTEM: Wajah yang terdeteksi di depan kamera saat ini adalah "
                        f"{cached_person['name']} (confidence: {cached_person['confidence']:.1f}%). "
                        f"Gunakan informasi ini untuk menyapa mereka dengan nama dan memberikan "
                        f"respons yang lebih personal.]"
                    )
                    history.append({'role': 'user', 'content': context_msg})
                    session_state[session_id]['last_face'] = cached_person['name']
                    logger.info(f"Face context injected: {cached_person['name']} ({cached_person['confidence']:.1f}%)")
        else:
            # Reset when no face detected
            with _face_context_lock:
                session_state[session_id]['last_face'] = None

        # Add user message to history
        history.append({'role': 'user', 'content': message})

        # Trim history - keep first 4 (system context) + recent messages
        if len(history) > MAX_HISTORY_SIZE:
            # Simple: always keep first 4 (instructions+memory) + recent tail
            history[:] = history[:4] + history[-(MAX_HISTORY_SIZE-4):]

    # Emit status
    emit('ai_status', {'status': 'thinking'})

    try:
        if MULTI_AGENT_ENABLED:
            # Use multi-agent orchestrator
            logger.info(f"[{session_id}] Using multi-agent orchestrator")
            orchestrator.process(session_id, history, emit)
        else:
            # Use single-agent loop
            logger.info(f"[{session_id}] Using single-agent loop")
            _process_agent_loop(session_id, history)

    except Exception as e:
        error_str = str(e)
        logger.error(f"Error processing message: {e}")

        # Check if model rejected multimodal/image content
        if '400' in error_str or 'Bad Request' in error_str:
            # Model likely doesn't support images — give helpful message
            fallback = "Maaf, model AI yang digunakan saat ini tidak mendukung pemrosesan gambar (multimodal/vision). Gunakan model yang mendukung vision seperti Claude atau GPT-4o."
            history.append({'role': 'assistant', 'content': fallback})
            emit('ai_chunk', {'chunk': fallback})
            emit('ai_status', {'status': 'completed'})
        else:
            emit('error', {'message': f"Error: {error_str}"})
            emit('ai_status', {'status': 'error'})


# Start cleanup timer after handle_message is defined (fixes NameError)
_start_cleanup_timer()


def _process_agent_loop(session_id, history):
    """Tool-use agent loop: call AI, execute tools, repeat until text response"""
    MAX_ITERATIONS = 10

    for iteration in range(MAX_ITERATIONS):
        # Check stop flag with lock for thread-safe access
        with conversations_lock:
            should_stop = session_id in stop_flags
        if should_stop:
            logger.info(f"Stop requested for {session_id}, aborting")
            emit('ai_status', {'status': 'stopped'})
            return

        logger.info(f"Agent iteration {iteration + 1}/{MAX_ITERATIONS} for {session_id}")

        response_text = []
        tool_use = None

        for chunk in ai_client.chat_stream_with_tools(history):
            # Check stop flag with lock for thread-safe access
            with conversations_lock:
                should_stop = session_id in stop_flags
            if should_stop:
                logger.info(f"Stop requested during streaming for {session_id}")
                if response_text:
                    full = ''.join(response_text)
                    history.append({'role': 'assistant', 'content': full})
                emit('ai_status', {'status': 'stopped'})
                return

            chunk_type = chunk.get('type')

            if chunk_type == 'text':
                response_text.append(chunk['content'])
                emit('ai_chunk', {'chunk': chunk['content']})

            elif chunk_type == 'tool_use':
                tool_use = chunk
                break  # Stop streaming, execute tool first

            elif chunk_type == 'message_stop':
                # No tool use — final text response complete
                if response_text:
                    full = ''.join(response_text)
                    history.append({'role': 'assistant', 'content': full})
                emit('ai_status', {'status': 'completed'})
                logger.info(f"Agent done — text response sent to {session_id}")
                return

        # If loop exits without tool_use and without message_stop — stream gave nothing
        if not tool_use and not response_text:
            logger.warning(f"No response from AI in iteration {iteration + 1}")
            emit('ai_chunk', {'chunk': 'Maaf, AI tidak merespon. Silakan coba lagi.'})
            emit('ai_status', {'status': 'completed'})
            return

        if tool_use:
            tool_id = tool_use['id']
            tool_name = tool_use['name']
            tool_input = tool_use['input']

            logger.info(f"Tool use: {tool_name}({json.dumps(tool_input)})")
            emit('tool_executing', {
                'tool': tool_name,
                'input': json.dumps(tool_input)[:200]
            })

            # If AI sent text before tool_use, save it
            if response_text:
                full = ''.join(response_text)
                history.append({'role': 'assistant', 'content': full})
                response_text = []

            # Execute the tool
            result = agent_tools.execute(tool_name, tool_input)

            logger.info(f"Tool result: {result[:200]}")

            # Check if result is an image (JSON format from camera tool)
            is_image_result = False
            result_data = None
            try:
                # Check if it's strict JSON
                result_data = json.loads(result)
                if isinstance(result_data, dict) and result_data.get('type') == 'image':
                    is_image_result = True
            except (json.JSONDecodeError, TypeError):
                pass
                
            # Regex fallback: Some AI models wrap JSON in markdown or just return the URL
            import re
            if not is_image_result and '/api/image/' in result:
                # Try to extract the JSON if wrapped in markdown
                json_match = re.search(r'\{.*?"type":\s*"image".*?\}', result, re.DOTALL)
                if json_match:
                    try:
                        result_data = json.loads(json_match.group(0))
                        is_image_result = True
                    except:
                        pass
                
                # If still not true, just extract URL manually
                if not is_image_result:
                    url_match = re.search(r'(/api/image/[\w\d_.-]+)', result)
                    if url_match:
                        is_image_result = True
                        result_data = {
                            'type': 'image',
                            'url': url_match.group(1),
                            'description': 'Camera capture',
                            'filename': url_match.group(1).split('/')[-1]
                        }

            if is_image_result and result_data:
                # Emit special image event to frontend
                emit('tool_image', {
                    'tool': tool_name,
                    'image_url': result_data.get('url', ''),
                    'description': result_data.get('description', 'Kamera berhasil mengambil gambar'),
                    'width': result_data.get('width', 640),
                    'height': result_data.get('height', 480),
                    'filename': result_data.get('filename', '')
                })
                logger.info(f"Image emitted to frontend: {result_data.get('url')}")

            # Add assistant tool_use block to history
            history.append({
                'role': 'assistant',
                'content': [{
                    'type': 'tool_use',
                    'id': tool_id,
                    'name': tool_name,
                    'input': tool_input
                }]
            })

            # Add tool result as user message
            # For images, send as multimodal content block if model supports vision
            if is_image_result and result_data:
                if VISION_ENABLED:
                    base64_data = result_data.get('base64', '')
                    mime_type = result_data.get('mime_type', 'image/jpeg')
                    if base64_data:
                        # Send image to AI for analysis
                        history.append({
                            'role': 'user',
                            'content': [{
                                'type': 'tool_result',
                                'tool_use_id': tool_id,
                                'content': [{
                                    'type': 'image',
                                    'source': {
                                        'type': 'base64',
                                        'media_type': mime_type,
                                        'data': base64_data
                                    }
                                }]
                            }]
                        })
                        logger.info(f"Image sent as multimodal block to AI ({len(base64_data)} chars base64)")
                        # Note: base64 stays in current turn, will be trimmed when history exceeds MAX_HISTORY_SIZE
                    else:
                        # Fallback — no base64 available
                        history.append({
                            'role': 'user',
                            'content': [{
                                'type': 'tool_result',
                                'tool_use_id': tool_id,
                                'content': f"Image captured: {result_data.get('filename', 'unknown')} ({result_data.get('width', '?')}x{result_data.get('height', '?')})"
                            }]
                        })
                else:
                    # Vision disabled — tell model it cannot see images, must be honest
                    history.append({
                        'role': 'user',
                        'content': [{
                            'type': 'tool_result',
                            'tool_use_id': tool_id,
                            'content': (
                                f"Image saved: {result_data.get('filename')} "
                                f"({result_data.get('width')}x{result_data.get('height')}). "
                                f"You CANNOT see images. Say: 'Maaf, saya model text-only. Gambar sudah muncul di layar Anda.'"
                            )
                        }]
                    })
                    logger.info(f"Image result sent as text-only (vision disabled)")
            else:
                history.append({
                    'role': 'user',
                    'content': [{
                        'type': 'tool_result',
                        'tool_use_id': tool_id,
                        'content': result
                    }]
                })

            # Emit tool result to frontend (only if not image, or simplified version)
            if is_image_result:
                emit('tool_result', {
                    'tool': tool_name,
                    'result': f"✅ Image captured: {result_data.get('filename', 'camera.jpg')}"
                })
            else:
                emit('tool_result', {
                    'tool': tool_name,
                    'result': result[:500]
                })

            # Removed time.sleep(0.1) - no rate limiting needed, just adds latency

            # Continue loop — AI will process tool result and either text or more tools
            continue

    # Max iterations reached - add informative message to history
    logger.warning(f"Max agent iterations ({MAX_ITERATIONS}) reached for {session_id}")
    error_msg = "Maaf, saya mencapai batas maksimum iterasi tool. Silakan coba pertanyaan yang lebih spesifik atau sederhana."
    history.append({'role': 'assistant', 'content': error_msg})
    emit('ai_chunk', {'chunk': error_msg})
    emit('ai_status', {'status': 'completed'})
    emit('error', {'message': 'Max tool iterations reached'})


@socketio.on('stop_generation')
def handle_stop_generation():
    """Client requests to stop the current AI generation"""
    session_id = request.sid
    logger.info(f"Stop generation requested by {session_id}")
    with conversations_lock:
        stop_flags.add(session_id)
    emit('generation_stopped')


@socketio.on('request_tts')
def handle_request_tts(data):
    """Generate TTS and emit base64 audio via socket (bypasses adblockers)"""
    session_id = request.sid
    text = data.get('text', '')
    if not text:
        emit('tts_error', {'error': 'No text'})
        return

    try:
        os.makedirs('/home/elektro/ai-audio/static/audio', exist_ok=True)
        filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join('/home/elektro/ai-audio/static/audio', filename)

        import subprocess
        result = subprocess.run(
            [
                os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'edge-tts'),
                '--voice', 'id-ID-ArdiNeural',
                '--text', text,
                '--write-media', filepath,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"edge-tts failed: {result.stderr[:200]}")

        import base64
        with open(filepath, 'rb') as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')

        emit('tts_audio', {'base64': audio_b64})
    except Exception as e:
        logger.error(f"TTS socket error: {e}")
        emit('tts_error', {'error': str(e)})


@socketio.on('audio_data')
def handle_audio(audio_data):
    """
    Process audio from client, convert to text via server-side speech recognition.
    Optimized: bypasses pydub overhead, uses persistent HTTP session for Google STT.
    """
    global _audio_processing_count
    session_id = request.sid
    t0 = time.time()
    data_size = len(audio_data) if audio_data else 0

    with _audio_processing_lock:
        _audio_processing_count += 1
        concurrent = _audio_processing_count

    logger.info(f"Received audio from {session_id}, size={data_size}B, concurrent={concurrent}")

    emit('audio_status', {'status': 'processing'})

    webm_path = None
    flac_path = None

    try:
        # Write webm audio to temp file
        webm_fd, webm_path = tempfile.mkstemp(suffix='.webm')
        with os.fdopen(webm_fd, 'wb') as f:
            f.write(audio_data)
        t1 = time.time()
        logger.info(f"  write temp: {(t1-t0)*1000:.0f}ms")

        # Convert webm -> flac (16kHz mono) using ffmpeg directly (bypasses pydub overhead)
        # FLAC is what Google STT expects natively — avoids extra WAV->FLAC conversion inside recognize_google()
        flac_path = webm_path.replace('.webm', '.flac')
        result = _subprocess.run(
            ['ffmpeg', '-y', '-i', webm_path, '-ar', '16000', '-ac', '1',
             '-sample_fmt', 's16', '-f', 'flac', flac_path],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:200]}")
        t2 = time.time()
        logger.info(f"  ffmpeg webm->flac: {(t2-t1)*1000:.0f}ms")

        # Read FLAC data and call Google STT directly via persistent session (connection pooling)
        with open(flac_path, 'rb') as f:
            flac_data = f.read()

        stt_url = (
            f"{_GOOGLE_STT_URL}?client=chromium"
            f"&lang=id-ID&key={_GOOGLE_STT_KEY}&pfilter=0"
        )
        stt_resp = _stt_session.post(
            stt_url,
            data=flac_data,
            headers={'Content-Type': 'audio/x-flac; rate=16000'},
            timeout=10,
        )
        t3 = time.time()
        logger.info(f"  Google STT (pooled): {(t3-t2)*1000:.0f}ms, total: {(t3-t0)*1000:.0f}ms")

        # Parse Google STT response (same format as speech_recognition library)
        response_text = stt_resp.text
        # Google returns multiple JSON lines; the actual result is in the line with "result" key
        actual_result = None
        for line in response_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if 'result' in parsed and len(parsed['result']) > 0:
                    actual_result = parsed
                    break
            except json.JSONDecodeError:
                continue

        if actual_result is None:
            logger.debug("No speech result (silence/unintelligible)")
            emit('audio_silence')
            return

        # Extract transcript from nested result structure
        alternatives = actual_result['result'][0].get('alternative', [])
        if not alternatives:
            emit('audio_silence')
            return

        text = alternatives[0].get('transcript', '').strip()
        confidence = alternatives[0].get('confidence', 0)
        logger.info(f"  Speech recognized: \"{text}\" (confidence: {confidence:.2f})")

        if text:
            emit('audio_result', {'text': text})
        else:
            emit('audio_silence')

    except _requests.exceptions.Timeout:
        logger.error("Google STT request timed out (>10s)")
        emit('audio_error', {'message': 'Speech API timeout — coba bicara lebih pendek'})
    except _requests.exceptions.ConnectionError as e:
        logger.error(f"Google STT connection error: {e}")
        emit('audio_error', {'message': 'Speech API connection failed'})
    except Exception as e:
        logger.error(f"Audio processing error: {e}", exc_info=True)
        emit('audio_error', {'message': f'Error: {str(e)}'})
    finally:
        with _audio_processing_lock:
            _audio_processing_count -= 1

        # Clean temp files
        for path in [webm_path, flac_path]:
            if path:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except Exception as e:
                    logger.debug(f"Failed to clean temp file {path}: {e}")


def open_browser(port):
    """Open browser in fullscreen mode after server starts"""
    import webbrowser
    import subprocess

    time.sleep(2)  # Wait for server to be ready

    url = f'https://localhost:{port}'
    logger.info(f"Opening browser at {url}")

    try:
        # Try to open with Brave/Chrome/Chromium in fullscreen mode (kiosk mode)
        chrome_commands = [
            ['brave-browser', '--no-sandbox', '--kiosk', '--start-fullscreen', '--ignore-certificate-errors', '--autoplay-policy=no-user-gesture-required', url],
            ['brave', '--no-sandbox', '--kiosk', '--start-fullscreen', '--ignore-certificate-errors', '--autoplay-policy=no-user-gesture-required', url],
            ['google-chrome', '--no-sandbox', '--kiosk', '--start-fullscreen', '--ignore-certificate-errors', '--autoplay-policy=no-user-gesture-required', url],
            ['chromium-browser', '--no-sandbox', '--kiosk', '--start-fullscreen', '--ignore-certificate-errors', '--autoplay-policy=no-user-gesture-required', url],
            ['chromium', '--no-sandbox', '--kiosk', '--start-fullscreen', '--ignore-certificate-errors', '--autoplay-policy=no-user-gesture-required', url],
        ]

        opened = False
        for cmd in chrome_commands:
            try:
                # Capture stderr to log any errors
                result = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=dict(os.environ, DISPLAY=':0')
                )
                opened = True
                logger.info(f"Opened with {cmd[0]} in fullscreen mode (PID: {result.pid})")
                break
            except FileNotFoundError:
                logger.debug(f"{cmd[0]} not found")
                continue
            except Exception as e:
                logger.error(f"Failed to open {cmd[0]}: {e}")
                continue

        if not opened:
            # Fallback to default browser (won't be fullscreen)
            webbrowser.open(url)
            logger.info("Opened with default browser (fullscreen may not be supported)")

    except Exception as e:
        logger.error(f"Failed to open browser: {e}")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 15000))
    logger.info(f"Starting Voice AI Chat Web Server on port {port}")
    logger.info(f"AI API: {ai_client.api_url}")
    logger.info(f"Model: {ai_client.model}")

    # Start background face scanner thread
    scanner_thread = threading.Thread(
        target=background_face_scanner,
        args=(face_engine, socketio, scanner_stop_flag),
        daemon=True
    )
    scanner_thread.start()
    logger.info("Background face scanner started")

    # Start browser opener in background thread
    browser_thread = threading.Thread(target=open_browser, args=(port,), daemon=True)
    browser_thread.start()

    socketio.run(app, host='0.0.0.0', port=port, debug=False,
                 keyfile='key.pem', certfile='cert.pem')
