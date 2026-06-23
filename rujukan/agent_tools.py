import subprocess
import os
import logging
import json
import time
import shlex
import tempfile
import uuid
import base64
import re
from datetime import datetime
from memory import save_memory_entry

logger = logging.getLogger(__name__)

DANGEROUS_PATTERNS = [
    'rm -rf / ', 'rm -rf /*', 'rm -fr / ', 'rm -fr /*',
    '> /dev/sda', '> /dev/nvme', '> /dev/hd',
    'mkfs',
    'dd if=',
    ':(){ :|:& };:',
    '/dev/zero of=/dev/',
    'fdisk /dev/',
    'parted /dev/',
    'wipefs',
    'shred /dev/',
]

READ_PATHS = ['/home/elektro/', '/tmp/', '/var/log/', '/etc/', '/root']
WRITE_PATHS = ['/home/elektro/', '/tmp/', '/root']

TOOLS = [
    {
        "name": "run_command",
        "description": "Execute a shell command on the Ubuntu 24.04 server and return stdout, stderr, exit code. Use for: checking system state, managing services, reading logs, disk/ram/cpu checks, restarting services, checking processes. Max 30 second timeout. Be specific with commands — use absolute paths when possible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute (e.g. 'df -h', 'systemctl status nginx', 'free -h')"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "capture_camera",
        "description": "Capture photo from USB camera. Returns image that will be displayed in chat. Use for: taking photos, visual inspection, monitoring, documentation. Image saved temporarily and shown to user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device": {
                    "type": "integer",
                    "description": "Camera device index (default 0 for first camera)",
                    "default": 0
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what you're capturing (e.g. 'Current view of server room')"
                }
            },
            "required": []
        }
    },
    {
        "name": "capture_cctv",
        "description": "Capture frame from RTSP CCTV camera. Returns image that will be displayed in chat. Use for: monitoring CCTV feeds, checking security cameras, viewing remote locations. Configure cameras in .env file (RTSP_URL_1, RTSP_URL_2, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "integer",
                    "description": "CCTV camera ID (1 for RTSP_URL_1, 2 for RTSP_URL_2, etc). Default 1.",
                    "default": 1
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what you're capturing (e.g. 'Front door CCTV view')"
                }
            },
            "required": []
        }
    },
    {
        "name": "read_image",
        "description": "Read an image file from the server filesystem and show it for visual analysis. Supports jpg, png, gif, bmp, webp. The image will be displayed to the user and analyzed if the AI model supports vision. Use for: viewing saved photos, screenshots, downloaded images, inspecting any image on disk. Max 10MB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the image file (e.g. '/home/elektro/Pictures/screenshot.png', '/tmp/camera_20250101_120000.jpg')"
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what this image shows or why you're reading it"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read contents of a file from the server filesystem. Use for: checking config files, reading logs, inspecting application state. Returns file contents as text. Max 10MB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-indexed). Default 0."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Default 100."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or overwrite content to a file. Restricted to /home/elektro/ and /tmp/ directories for safety.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to write to (must be under /home/elektro/ or /tmp/)"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory on the server. Shows files, subdirectories, sizes, and permissions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the directory to list (e.g. '/home/elektro/', '/var/log/')"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "get_system_info",
        "description": "Get current system information: CPU cores, RAM usage (free/used/total), disk space (all mounts), system uptime, and load averages.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "manage_service",
        "description": "Manage a systemd service on the Ubuntu server: check status, start, stop, restart, or enable/disable. Requires sudo for start/stop/restart.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the systemd service (e.g. 'nginx', 'docker', 'ssh')"
                },
                "action": {
                    "type": "string",
                    "enum": ["status", "start", "stop", "restart", "enable", "disable"],
                    "description": "Action to perform on the service"
                }
            },
            "required": ["service_name", "action"]
        }
    },
    {
        "name": "get_processes",
        "description": "List top running processes sorted by CPU usage. Shows PID, user, CPU%, MEM%, and command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of top processes to show. Default 15."
                }
            },
            "required": []
        }
    },
    {
        "name": "save_memory",
        "description": "Save personal information about the user to persistent memory for future conversations. Use ONLY for: user preferences, personality traits, facts about the user, communication style, personal decisions. Do NOT use for technical AI instructions or capability descriptions — those belong in instructions.md. File: memory.md",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Short topic/title for this memory entry (e.g. 'User Preferences', 'Communication Style')"
                },
                "content": {
                    "type": "string",
                    "description": "The personal information to remember about the user"
                }
            },
            "required": ["topic", "content"]
        }
    },
    {
        "name": "control_lamp",
        "description": "Control an ESP32 lamp via MQTT. Turn lamp on, off, or toggle. Lamp name can be in Bahasa Indonesia (e.g., 'ruang tamu', 'kamar tidur', 'dapur'). Returns the lamp's new state after the action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lamp_name": {
                    "type": "string",
                    "description": "Name of the lamp to control (e.g., 'ruang tamu', 'kamar', 'dapur'). Case-insensitive, supports aliases from lamp_config.json."
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "toggle"],
                    "description": "Action to perform: 'on' to turn on, 'off' to turn off, 'toggle' to switch state."
                }
            },
            "required": ["lamp_name", "action"]
        }
    },
    {
        "name": "get_lamp_status",
        "description": "Get the current status (on/off/unknown) of a specific lamp or all lamps. Returns cached state from MQTT messages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lamp_name": {
                    "type": "string",
                    "description": "Name of the lamp to query. If omitted or empty, returns status of all lamps."
                }
            },
            "required": []
        }
    },
    {
        "name": "list_lamps",
        "description": "List all configured lamps with their names, locations, aliases, and current status. Useful for discovering available lamps before controlling them.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


class AgentTools:
    def __init__(self):
        self.execution_count = 0

        # Initialize MQTT service and load lamp config
        self.mqtt_service = None
        self.lamp_config = None

        try:
            from mqtt_service import MQTTService
            self.mqtt_service = MQTTService()
            self.mqtt_service.connect()

            # Load lamp configuration
            config_path = os.path.join(os.path.dirname(__file__), 'lamp_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.lamp_config = json.load(f)
                logger.info(f"Loaded {len(self.lamp_config.get('lamps', []))} lamps from config")
            else:
                logger.warning("lamp_config.json not found, lamp control disabled")
        except Exception as e:
            logger.error(f"Failed to initialize lamp control: {e}")

    def _log_execution(self, tool_name, tool_input, result_preview):
        self.execution_count += 1
        logger.info(f"[TOOL #{self.execution_count}] {tool_name}({json.dumps(tool_input)}) → {result_preview[:120]}")

    def _is_command_safe(self, command):
        lower = command.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in lower:
                return False, f"DANGER: Command blocked — matches dangerous pattern '{pattern}'"
        return True, ""

    def _is_path_safe(self, path, write=False):
        # Use realpath to resolve symlinks and prevent path traversal attacks
        abs_path = os.path.realpath(path)
        allowed = WRITE_PATHS if write else READ_PATHS
        for safe in allowed:
            safe_real = os.path.realpath(safe.rstrip('/'))
            if abs_path == safe_real or abs_path.startswith(safe_real + os.sep):
                return True, abs_path
        action = "write to" if write else "read"
        return False, f"ERROR: Path '{path}' is outside allowed directories for {action}. Must be under: {', '.join(allowed)}"

    def _find_lamp(self, lamp_name):
        """Find lamp configuration by name, ID, or alias (case-insensitive)."""
        if not self.lamp_config:
            return None

        lamp_name_lower = lamp_name.lower().strip()

        for lamp in self.lamp_config.get('lamps', []):
            if lamp['id'].lower() == lamp_name_lower:
                return lamp
            if lamp['name'].lower() == lamp_name_lower:
                return lamp
            if lamp_name_lower in [alias.lower() for alias in lamp.get('aliases', [])]:
                return lamp

        return None

    def execute(self, tool_name, tool_input):
        method = getattr(self, f'_tool_{tool_name}', None)
        if not method:
            result = f"ERROR: Unknown tool '{tool_name}'"
            self._log_execution(tool_name, tool_input, result)
            return result

        try:
            result = method(tool_input)
            self._log_execution(tool_name, tool_input, result)
            return result
        except Exception as e:
            result = f"ERROR executing {tool_name}: {str(e)}"
            self._log_execution(tool_name, tool_input, result)
            return result

    def _tool_run_command(self, inp):
        cmd = inp.get('command', '')
        if not cmd:
            return "ERROR: No command provided"

        safe, reason = self._is_command_safe(cmd)
        if not safe:
            return reason

        try:
            args = shlex.split(cmd)
            result = subprocess.run(
                args, shell=False, capture_output=True, text=True,
                timeout=30, env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            parts = []
            if out:
                parts.append(f"stdout:\n{out}")
            if err:
                parts.append(f"stderr:\n{err}")
            parts.append(f"exit_code: {result.returncode}")
            return "\n".join(parts) if parts else "exit_code: 0 (no output)"
        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out after 30 seconds"
        except ValueError as e:
            return f"ERROR: Invalid command syntax: {e}"

    def _tool_read_file(self, inp):
        path = inp.get('path', '')
        if not path:
            return "ERROR: No path provided"

        safe, abs_path = self._is_path_safe(path, write=False)
        if not safe:
            return abs_path

        if not os.path.exists(abs_path):
            return f"ERROR: File not found: {path}"

        size = os.path.getsize(abs_path)
        if size > 10 * 1024 * 1024:
            return f"ERROR: File too large ({size} bytes, max 10MB)"

        # Validate offset and limit parameters
        offset = inp.get('offset', 0)
        limit = inp.get('limit', 100)

        if not isinstance(offset, int) or offset < 0:
            return f"ERROR: Invalid offset '{offset}' - must be non-negative integer"

        if not isinstance(limit, int) or limit <= 0:
            return f"ERROR: Invalid limit '{limit}' - must be positive integer"

        if limit > 10000:
            return f"ERROR: Limit '{limit}' exceeds maximum allowed value (10000)"

        try:
            with open(abs_path, 'r', errors='replace') as f:
                lines = f.readlines()

            total = len(lines)
            sliced = lines[offset:offset + limit]

            header = f"File: {path} | Lines {offset}-{offset + len(sliced)} of {total} | Size: {size} bytes\n"
            return header + "".join(sliced)
        except PermissionError:
            return f"ERROR: Permission denied reading {abs_path}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def _tool_write_file(self, inp):
        path = inp.get('path', '')
        content = inp.get('content', '')

        if not path:
            return "ERROR: No path provided"

        # Validate content size
        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            return f"ERROR: Content too large ({len(content)} bytes, max 10MB)"

        safe, abs_path = self._is_path_safe(path, write=True)
        if not safe:
            return abs_path

        dir_path = os.path.dirname(abs_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        try:
            with open(abs_path, 'w') as f:
                f.write(content)
            return f"OK: Wrote {len(content)} bytes to {path}"
        except PermissionError:
            return f"ERROR: Permission denied writing to {path}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def _tool_list_directory(self, inp):
        path = inp.get('path', '/home/elektro/')
        if not os.path.exists(path):
            return f"ERROR: Directory not found: {path}"

        try:
            items = []
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        stat = entry.stat()
                        kind = 'D' if entry.is_dir() else 'F'
                        size = stat.st_size
                        mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(stat.st_mtime))
                        items.append({
                            'name': entry.name,
                            'type': kind,
                            'size': size,
                            'mtime': mtime
                        })
                    except OSError:
                        pass

            items.sort(key=lambda x: (x['type'], x['name']))
            lines = [f"Directory: {path} | {len(items)} items\n"]
            for item in items:
                size_str = f"{item['size']:>10,}" if item['type'] == 'F' else "       <DIR>"
                lines.append(f"  [{item['type']}] {item['name']:<40} {size_str}  {item['mtime']}")
            return "\n".join(lines)
        except PermissionError:
            return f"ERROR: Permission denied: {path}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def _tool_get_system_info(self, inp=None):
        try:
            # uptime
            up = subprocess.run(['uptime', '-p'], capture_output=True, text=True, timeout=5)
            uptime = up.stdout.strip()

            # CPU
            cpu = subprocess.run(['nproc'], capture_output=True, text=True, timeout=5)
            cores = cpu.stdout.strip()

            # load
            load = subprocess.run(['cat', '/proc/loadavg'], capture_output=True, text=True, timeout=5)
            load_avg = load.stdout.strip()

            # RAM
            mem = subprocess.run(['free', '-h'], capture_output=True, text=True, timeout=5)
            mem_out = mem.stdout.strip()

            # Disk
            disk = subprocess.run(['df', '-h', '/', '/home'], capture_output=True, text=True, timeout=5)
            disk_out = disk.stdout.strip()

            return f"""System Info:
    CPU Cores: {cores}
    Uptime: {uptime}
    Load: {load_avg}

    Memory:
    {mem_out}

    Disk:
    {disk_out}"""
        except Exception as e:
            return f"ERROR: {str(e)}"

    def _tool_manage_service(self, inp):
        service = inp.get('service_name', '')
        action = inp.get('action', 'status')
        if not service:
            return "ERROR: No service_name provided"
        valid_actions = ['status', 'start', 'stop', 'restart', 'enable', 'disable']
        if action not in valid_actions:
            return f"ERROR: Invalid action '{action}'. Allowed: {', '.join(valid_actions)}"

        cmd = ['sudo', 'systemctl', action, service]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            out = result.stdout.strip()
            err = result.stderr.strip()
            parts = []
            if out:
                parts.append(out)
            if err:
                parts.append(err)
            parts.append(f"exit_code: {result.returncode}")
            return "\n".join(parts)
        except subprocess.TimeoutExpired:
            return "ERROR: systemctl timed out after 15 seconds"

    def _tool_get_processes(self, inp):
        limit = inp.get('limit', 15) if inp else 15
        if not isinstance(limit, int) or limit < 1:
            limit = 15
        if limit > 100:
            limit = 100
        try:
            ps = subprocess.run(
                ['ps', 'aux', '--sort=-%cpu'],
                capture_output=True, text=True, timeout=10
            )
            lines = ps.stdout.strip().split('\n') if ps.stdout else []
            header = lines[0] if lines else ''
            body = lines[1:limit + 1] if len(lines) > 1 else []
            return '\n'.join([header] + body) if header else "No processes found"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def _tool_save_memory(self, inp):
        topic = inp.get('topic', '')
        content = inp.get('content', '')
        if not topic or not content:
            return "ERROR: Both 'topic' and 'content' are required"
        return save_memory_entry(topic, content)

    def _tool_capture_camera(self, inp):
        """Capture photo from USB camera using OpenCV"""
        from face_engine import camera_lock  # Import camera_lock to prevent conflicts

        device = inp.get('device', 0)
        description = inp.get('description', 'Camera capture')

        try:
            import cv2
        except ImportError:
            return "ERROR: OpenCV not installed. Run: pip install opencv-python"

        try:
            # Use camera_lock to prevent conflicts with background scanner
            with camera_lock:
                cap = cv2.VideoCapture(device)
                ret = False
                frame = None
                try:
                    if not cap.isOpened():
                        return f"ERROR: Cannot open camera device {device}. Check if camera is connected."

                    # Allow camera to warm up
                    time.sleep(0.5)

                    # Capture frame
                    ret, frame = cap.read()
                finally:
                    # Always release camera, even if exception occurs
                    cap.release()

            if not ret or frame is None:
                return "ERROR: Failed to capture image from camera"

            # Create unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"camera_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join('/tmp', filename)

            # Save image
            cv2.imwrite(filepath, frame)

            # Read back for base64 encoding
            _, img_bytes = cv2.imencode('.jpg', frame)
            img_b64 = base64.b64encode(img_bytes.tobytes()).decode('utf-8')

            # Get image dimensions
            height, width = frame.shape[:2]

            logger.info(f"Camera image captured: {filepath} ({width}x{height})")

            # Return special format that frontend will recognize as image
            return json.dumps({
                "type": "image",
                "path": filepath,
                "filename": filename,
                "url": f"/api/image/{filename}",
                "width": width,
                "height": height,
                "description": description,
                "timestamp": timestamp,
                "base64": img_b64,
                "mime_type": "image/jpeg"
            })

        except Exception as e:
            logger.error(f"Camera capture error: {e}")
            return f"ERROR: Camera capture failed: {str(e)}"

    def _tool_capture_cctv(self, inp):
        """Capture frame from RTSP CCTV stream"""
        import cv2

        camera_id = inp.get('camera_id', 1)
        description = inp.get('description', 'CCTV capture')

        # Get RTSP URL from environment
        rtsp_url = os.getenv(f'RTSP_URL_{camera_id}')
        camera_name = os.getenv(f'RTSP_NAME_{camera_id}', f'CCTV {camera_id}')

        if not rtsp_url:
            available = [k for k in os.environ if k.startswith('RTSP_URL_')]
            if not available:
                return "ERROR: No CCTV cameras configured. Add RTSP_URL_1, RTSP_URL_2, etc to .env file."
            return f"ERROR: Camera {camera_id} not configured. Available: {', '.join(available)}"

        try:
            # Connect to RTSP stream (no lock needed - network stream allows multiple connections)
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

            # Set timeout for connection (10 seconds)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)

            if not cap.isOpened():
                return f"ERROR: Cannot connect to {camera_name} ({rtsp_url}). Check network or credentials."

            # Read frame
            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return f"ERROR: Failed to capture frame from {camera_name}. Stream may be unavailable."

            # Create unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"cctv{camera_id}_{timestamp}.jpg"
            filepath = os.path.join('/tmp', filename)

            # Save image
            cv2.imwrite(filepath, frame)

            # Encode to base64 for AI vision
            _, buffer = cv2.imencode('.jpg', frame)
            img_b64 = base64.b64encode(buffer).decode('utf-8')

            # Get image dimensions
            height, width = frame.shape[:2]

            logger.info(f"CCTV {camera_id} captured: {filepath} ({width}x{height})")

            # Return special format that frontend will recognize as image
            return json.dumps({
                "type": "image",
                "source": "cctv",
                "camera_id": camera_id,
                "camera_name": camera_name,
                "path": filepath,
                "filename": filename,
                "url": f"/api/image/{filename}",
                "width": width,
                "height": height,
                "description": description,
                "timestamp": timestamp,
                "base64": img_b64,
                "mime_type": "image/jpeg"
            })

        except Exception as e:
            logger.error(f"CCTV capture error: {e}")
            return f"ERROR: CCTV capture failed - {str(e)}"

    def _tool_read_image(self, inp):
        """Read an image file from disk and return as base64"""
        path = inp.get('path', '')
        description = inp.get('description', 'Image from disk')

        if not path:
            return "ERROR: No path provided"

        safe, reason = self._is_path_safe(path, write=False)
        if not safe:
            return reason

        if not os.path.exists(path):
            return f"ERROR: File not found: {path}"

        size = os.path.getsize(path)
        if size > 10 * 1024 * 1024:
            return f"ERROR: File too large ({size} bytes, max 10MB)"

        # Detect mime type from extension
        ext = os.path.splitext(path)[1].lower()
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        mime_type = mime_map.get(ext)
        if not mime_type:
            return f"ERROR: Unsupported image format '{ext}'. Supported: {', '.join(mime_map.keys())}"

        filename = os.path.basename(path)

        # Read raw file bytes for base64 (avoids BGR decode→re-encode corruption)
        try:
            with open(path, 'rb') as f:
                raw_bytes = f.read()
        except Exception as e:
            return f"ERROR: Cannot read file: {str(e)}"

        img_b64 = base64.b64encode(raw_bytes).decode('utf-8')

        # Get dimensions
        width, height = 0, 0
        try:
            import cv2
            frame = cv2.imread(path)
            if frame is not None:
                height, width = frame.shape[:2]
        except ImportError:
            pass

        if width == 0 or height == 0:
            try:
                from PIL import Image
                with Image.open(path) as img:
                    width, height = img.size
            except ImportError:
                pass

        # Copy to /tmp/ so it's served via /api/image/
        safe_filename = re.sub(r'[^\w\d_.-]', '_', filename)
        dest = os.path.join('/tmp', safe_filename)
        if not os.path.exists(dest):
            try:
                import shutil
                shutil.copy2(path, dest)
            except Exception:
                pass

        logger.info(f"Image read from disk: {path} ({width}x{height})")

        return json.dumps({
            "type": "image",
            "path": dest,
            "filename": safe_filename,
            "url": f"/api/image/{safe_filename}",
            "width": width,
            "height": height,
            "description": description,
            "base64": img_b64,
            "mime_type": mime_type
        })

    def _tool_control_lamp(self, inp):
        """Control an ESP32 lamp via MQTT."""
        lamp_name = inp.get('lamp_name', '').strip()
        action = inp.get('action', '').lower().strip()

        if not lamp_name:
            return "Error: lamp_name is required"

        if action not in ['on', 'off', 'toggle']:
            return f"Error: Invalid action '{action}'. Must be 'on', 'off', or 'toggle'."

        lamp = self._find_lamp(lamp_name)

        if not lamp:
            if self.lamp_config:
                available = [l['name'] for l in self.lamp_config.get('lamps', [])]
                return f"Error: Lamp '{lamp_name}' not found. Available lamps: {', '.join(available)}"
            else:
                return "Error: Lamp configuration not loaded. Check lamp_config.json."

        if not self.mqtt_service or not self.mqtt_service.connected:
            return f"Error: MQTT service not connected. Cannot control lamp '{lamp['name']}'."

        command_topic = lamp['command_topic']
        success = self.mqtt_service.publish(command_topic, action)

        if not success:
            return f"Error: Failed to publish command to lamp '{lamp['name']}'."

        # Removed time.sleep(0.5) - MQTT state update is cached, no wait needed
        new_state = self.mqtt_service.get_lamp_state(lamp['name'])

        return json.dumps({
            'success': True,
            'lamp_name': lamp['name'],
            'location': lamp.get('location', 'Unknown'),
            'action': action,
            'new_state': new_state,
            'message': f"Lampu {lamp['name']} ({lamp.get('location', '')}) berhasil di-{action}. Status: {new_state}"
        })

    def _tool_get_lamp_status(self, inp):
        """Get status of one or all lamps."""
        lamp_name = inp.get('lamp_name', '').strip()

        if not self.mqtt_service:
            return "Error: MQTT service not initialized."

        if lamp_name:
            lamp = self._find_lamp(lamp_name)

            if not lamp:
                if self.lamp_config:
                    available = [l['name'] for l in self.lamp_config.get('lamps', [])]
                    return f"Error: Lamp '{lamp_name}' not found. Available lamps: {', '.join(available)}"
                else:
                    return "Error: Lamp configuration not loaded."

            state = self.mqtt_service.get_lamp_state(lamp['name'])

            return json.dumps({
                'lamp_name': lamp['name'],
                'location': lamp.get('location', 'Unknown'),
                'state': state,
                'message': f"Lampu {lamp['name']} ({lamp.get('location', '')}) status: {state}"
            })
        else:
            if not self.lamp_config:
                return "Error: Lamp configuration not loaded."

            all_states = self.mqtt_service.get_all_states()

            lamp_statuses = []
            for lamp in self.lamp_config.get('lamps', []):
                state = all_states.get(lamp['name'], 'unknown')
                lamp_statuses.append({
                    'name': lamp['name'],
                    'location': lamp.get('location', 'Unknown'),
                    'state': state
                })

            if not lamp_statuses:
                return "Tidak ada lampu yang dikonfigurasi."

            lines = ["Status semua lampu:"]
            for status in lamp_statuses:
                lines.append(f"- {status['name']} ({status['location']}): {status['state']}")

            return json.dumps({
                'lamps': lamp_statuses,
                'message': '\n'.join(lines)
            })

    def _tool_list_lamps(self, inp):
        """List all configured lamps."""
        if not self.lamp_config:
            return "Error: Lamp configuration not loaded. Check lamp_config.json."

        lamps = self.lamp_config.get('lamps', [])

        if not lamps:
            return "Tidak ada lampu yang dikonfigurasi."

        all_states = self.mqtt_service.get_all_states() if self.mqtt_service else {}

        lamp_list = []
        for lamp in lamps:
            state = all_states.get(lamp['name'], 'unknown')
            lamp_list.append({
                'id': lamp['id'],
                'name': lamp['name'],
                'location': lamp.get('location', 'Unknown'),
                'aliases': lamp.get('aliases', []),
                'state': state,
                'enabled': lamp.get('enabled', True)
            })

        lines = [f"Daftar lampu ({len(lamp_list)} total):"]
        for lamp in lamp_list:
            enabled_str = "" if lamp['enabled'] else " [DISABLED]"
            lines.append(f"- {lamp['name']} ({lamp['location']}): {lamp['state']}{enabled_str}")
            if lamp['aliases']:
                lines.append(f"  Alias: {', '.join(lamp['aliases'])}")

        return json.dumps({
            'lamps': lamp_list,
            'count': len(lamp_list),
            'message': '\n'.join(lines)
        })