"""
Agent Classes: BaseAgent and specialized agents for multi-agent orchestration.
Each agent has specific tools and system prompts tailored to their role.
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from socketio import Server as SocketIO

from ai_client import AIClient
from agent_tools import AgentTools, TOOLS
from .config import AgentConfig
from .task_context import TaskContext

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for all specialized agents.
    Provides tool-use loop, filtered tool access, and streaming support.
    """

    def __init__(
        self,
        agent_id: str,
        ai_client: AIClient,
        agent_tools: AgentTools,
        socketio: SocketIO,
        config: AgentConfig
    ):
        """
        Initialize base agent.

        Args:
            agent_id: Unique agent identifier
            ai_client: AI client for API calls
            agent_tools: Tool execution engine
            socketio: SocketIO instance for streaming
            config: Agent-specific configuration
        """
        self.agent_id = agent_id
        self.ai_client = ai_client
        self.agent_tools = agent_tools
        self.socketio = socketio
        self.config = config
        self.model = config.model or ai_client.model
        self.system_prompt = config.system_prompt
        self.max_iterations = config.max_iterations
        self.timeout = config.timeout

        # Determine allowed tools
        if config.allowed_tools == '*':
            self.allowed_tools = [t['name'] for t in TOOLS]
        else:
            self.allowed_tools = config.allowed_tools

        # Cache filtered tools (avoid rebuilding list every iteration)
        self._cached_tools = [t for t in TOOLS if t['name'] in self.allowed_tools]

    def get_filtered_tools(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions filtered for this agent (cached).

        Returns:
            List of tool definitions in Anthropic format
        """
        return self._cached_tools

    def process(
        self,
        history: List[Dict[str, Any]],
        context: TaskContext,
        emit_fn: Callable,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Process task with this agent using tool-use loop.

        Args:
            history: Conversation history (Anthropic format)
            context: Shared task context
            emit_fn: SocketIO emit function
            session_id: WebSocket session ID

        Returns:
            {
                'success': bool,
                'output': str,
                'tools_used': list,
                'context_updates': dict
            }
        """
        context.current_agent = self.agent_id
        tools_used = []
        response_text = []

        logger.info(f"[{self.agent_id}] Processing with {len(self.allowed_tools)} tools available")

        try:
            for iteration in range(self.max_iterations):
                t_iter_start = time.time()
                logger.info(f"[{self.agent_id}] Iteration {iteration + 1}/{self.max_iterations}")

                # Call AI with filtered tools
                agent_tools_list = self.get_filtered_tools() if self.allowed_tools is not None else None

                t_ai_start = time.time()
                for chunk in self.ai_client.chat_stream_with_tools(
                    history,
                    tools=agent_tools_list,
                    model=self.config.model
                ):
                    chunk_type = chunk.get('type')

                    if chunk_type == 'text':
                        text = chunk.get('content', '')
                        response_text.append(text)
                        emit_fn('ai_chunk', {
                            'chunk': text,
                            'agent': self.agent_id
                        })

                    elif chunk_type == 'tool_use':
                        t_ai_end = time.time()
                        logger.info(f"[{self.agent_id}] AI streaming took: {t_ai_end - t_ai_start:.2f}s")

                        tool_id = chunk['id']
                        tool_name = chunk['name']
                        tool_input = chunk['input']

                        logger.info(f"[{self.agent_id}] Tool use: {tool_name}({json.dumps(tool_input)[:100]})")
                        t_tool_start = time.time()

                        # Check tool access permission
                        if tool_name not in self.allowed_tools:
                            emit_fn('tool_executing', {
                                'tool': tool_name,
                                'input': json.dumps(tool_input)[:200],
                                'agent': self.agent_id,
                                'status': 'denied'
                            })
                            tool_result = f"ERROR: Tool '{tool_name}' not available to {self.agent_id} agent"
                        else:
                            emit_fn('tool_executing', {
                                'tool': tool_name,
                                'input': json.dumps(tool_input)[:200],
                                'agent': self.agent_id
                            })

                            # Execute tool
                            tool_result = self.agent_tools.execute(tool_name, tool_input)
                            t_tool_end = time.time()
                            logger.info(f"[{self.agent_id}] Tool '{tool_name}' execution: {t_tool_end - t_tool_start:.2f}s")
                            tools_used.append(tool_name)
                            context.add_tool_result(tool_name, tool_result)

                            # Check if tool result is an image (JSON format from camera tool)
                            is_image_result = False
                            result_data = None
                            try:
                                result_data = json.loads(tool_result)
                                if isinstance(result_data, dict) and result_data.get('type') == 'image':
                                    is_image_result = True
                            except (json.JSONDecodeError, TypeError):
                                pass

                            # Regex fallback for wrapped JSON
                            import re
                            if not is_image_result and '/api/image/' in tool_result:
                                json_match = re.search(r'\{.*?"type":\s*"image".*?\}', tool_result, re.DOTALL)
                                if json_match:
                                    try:
                                        result_data = json.loads(json_match.group(0))
                                        is_image_result = True
                                    except:
                                        pass

                                if not is_image_result:
                                    url_match = re.search(r'(/api/image/[\w\d_.-]+)', tool_result)
                                    if url_match:
                                        is_image_result = True
                                        result_data = {
                                            'type': 'image',
                                            'url': url_match.group(1),
                                            'description': 'Camera capture',
                                            'filename': url_match.group(1).split('/')[-1]
                                        }

                            # Emit tool_image event if image detected
                            if is_image_result and result_data:
                                emit_fn('tool_image', {
                                    'tool': tool_name,
                                    'image_url': result_data.get('url', ''),
                                    'description': result_data.get('description', 'Kamera berhasil mengambil gambar'),
                                    'width': result_data.get('width', 640),
                                    'height': result_data.get('height', 480),
                                    'filename': result_data.get('filename', ''),
                                    'agent': self.agent_id
                                })
                                logger.info(f"[{self.agent_id}] Image emitted to frontend: {result_data.get('url')}")

                        # Add tool result to history (removed success detection overhead)
                        history.append({
                            'role': 'user',
                            'content': [{
                                'type': 'tool_result',
                                'tool_use_id': tool_id,
                                'content': tool_result
                            }]
                        })

                        emit_fn('tool_result', {
                            'tool': tool_name,
                            'result': tool_result[:500],
                            'agent': self.agent_id
                        })

                        # Continue loop for more tool calls
                        break

                    elif chunk_type == 'message_stop':
                        t_ai_end = time.time()
                        t_iter_end = time.time()
                        logger.info(f"[{self.agent_id}] AI streaming took: {t_ai_end - t_ai_start:.2f}s")
                        logger.info(f"[{self.agent_id}] Total iteration: {t_iter_end - t_iter_start:.2f}s")

                        # No tool use - final response
                        full_response = ''.join(response_text)
                        history.append({'role': 'assistant', 'content': full_response})

                        return {
                            'success': True,
                            'output': full_response,
                            'tools_used': tools_used,
                            'context_updates': {}
                        }

                # Removed time.sleep(0.1) - no rate limiting needed, just adds latency

            # Max iterations reached
            logger.warning(f"[{self.agent_id}] Max iterations ({self.max_iterations}) reached")
            partial_response = ''.join(response_text) if response_text else 'Maaf, saya tidak bisa menyelesaikan tugas ini.'

            return {
                'success': False,
                'output': partial_response,
                'tools_used': tools_used,
                'context_updates': {},
                'error': 'Max iterations reached'
            }

        except Exception as e:
            logger.error(f"[{self.agent_id}] Agent error: {e}")
            return {
                'success': False,
                'output': '',
                'tools_used': tools_used,
                'context_updates': {},
                'error': str(e)
            }


class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent: Routes tasks, coordinates other agents, synthesizes results.
    Has NO direct tool access - only orchestration and fallback responses.
    """

    def __init__(self, ai_client: AIClient, socketio: SocketIO, config: AgentConfig):
        """
        Initialize supervisor agent.

        Args:
            ai_client: AI client instance
            socketio: SocketIO instance
            config: Supervisor configuration
        """
        # Supervisor doesn't need agent_tools
        super().__init__('supervisor', ai_client, None, socketio, config)

    def route(self, user_message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Decide which agent(s) should handle the task.
        OPTIMIZED: Uses keyword-based routing (instant) instead of AI call (~3-5s savings).
        AI routing only triggered when keywords yield very low confidence.

        Args:
            user_message: User's request
            history: Conversation history

        Returns:
            {
                'agent': str,  # Agent ID or 'supervisor'
                'confidence': float,  # 0.0-1.0
                'reasoning': str
            }
        """
        # Keyword-based routing only (instant, 0 API calls)
        # Vision queries → vision agent. Everything else → system agent (has ALL tools).
        # Removed AI fallback: keyword routing covers 100% of cases, saving ~3-5s per query.
        return self._keyword_route(user_message)

    def _keyword_route(self, message: str) -> Dict[str, Any]:
        """
        Simple keyword-based routing.
        Now simplified: most queries go to 'system' agent (has ALL tools).

        Args:
            message: User message

        Returns:
            Routing decision dict
        """
        message_lower = message.lower()

        # Vision queries need special handling (camera/image tools)
        vision_keywords = ['kamera', 'camera', 'foto', 'photo', 'gambar', 'image', 'cctv',
                          'wajah', 'face', 'capture', 'screenshot', 'lihat', 'rekam', 'video', 'ambil']
        if any(kw in message_lower for kw in vision_keywords):
            return {
                'agent': 'vision',
                'confidence': 0.8,
                'reasoning': 'Vision query detected'
            }

        # Everything else → system agent (has ALL tools: system + lamps + memory + etc)
        return {
            'agent': 'system',
            'confidence': 0.9,
            'reasoning': 'Default to system agent (has all tools)'
        }

    def synthesize(self, agent_results: List[Dict[str, Any]], emit_fn: Callable) -> str:
        """
        Synthesize results from multiple agents into a coherent response.

        Args:
            agent_results: List of agent execution results
            emit_fn: SocketIO emit function

        Returns:
            Synthesized response text
        """
        if len(agent_results) == 1:
            return agent_results[0].get('output', 'Task completed.')

        # Multiple agents - synthesize their results
        synthesis_prompt = "Synthesize these agent results into a coherent response in Bahasa Indonesia:\n\n"
        for i, result in enumerate(agent_results, 1):
            synthesis_prompt += f"Agent {i} ({result.get('agent', 'unknown')}):\n{result.get('output', 'No output')}\n\n"

        try:
            history = [{'role': 'user', 'content': synthesis_prompt}]
            response_text = []

            for chunk in self.ai_client.chat_stream_with_tools(history, tools=None, model=self.config.model):
                if chunk.get('type') == 'text':
                    text = chunk['content']
                    response_text.append(text)
                    emit_fn('ai_chunk', {'chunk': text, 'agent': 'supervisor'})
                elif chunk.get('type') == 'message_stop':
                    break

            return ''.join(response_text)

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            # Fallback: concatenate results
            return '\n\n'.join(r.get('output', '') for r in agent_results)


class VisionAgent(BaseAgent):
    """
    Vision Agent: Camera capture, CCTV monitoring, face recognition, image analysis.
    Tools: capture_camera, capture_cctv, read_image
    """

    def __init__(self, ai_client: AIClient, agent_tools: AgentTools, socketio: SocketIO, config: AgentConfig):
        super().__init__('vision', ai_client, agent_tools, socketio, config)

    def process(
        self,
        history: List[Dict[str, Any]],
        context: TaskContext,
        emit_fn: Callable,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Process vision tasks with fallback image capture.
        If AI API fails, automatically capture image when user intent is detected.
        """
        # Extract user message to detect intent
        user_message = ''
        for msg in reversed(history):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                break

        # Keywords indicating user wants to capture image
        capture_keywords = ['foto', 'gambar', 'camera', 'kamera', 'cctv', 'capture', 'ambil', 'lihat', 'rekam', 'video']
        wants_capture = any(keyword in user_message.lower() for keyword in capture_keywords)

        try:
            # Try normal processing with AI
            result = super().process(history, context, emit_fn, session_id)

            # Track captured image paths in context
            for tool_name in result.get('tools_used', []):
                if tool_name in ('capture_camera', 'capture_cctv'):
                    # Find the image path in tool results
                    for tr in context.tool_results:
                        if tr['tool'] == tool_name and 'image_path' in str(tr['result']):
                            try:
                                import json as _json
                                img_data = _json.loads(tr['result'])
                                if 'path' in img_data:
                                    context.images_captured.append(img_data['path'])
                            except (json.JSONDecodeError, KeyError):
                                pass

            # If AI failed but user wanted capture, attempt fallback
            if not result.get('success') and wants_capture and 'capture_camera' not in result.get('tools_used', []):
                logger.warning(f"[{self.agent_id}] AI failed but user wants capture, attempting fallback")
                self._fallback_capture(emit_fn, context)
                result['output'] = result.get('output', '') + '\n\n(Catatan: Model vision sedang tidak tersedia, tapi gambar berhasil diambil)'

            return result

        except Exception as e:
            logger.error(f"[{self.agent_id}] Vision agent error: {e}")

            # Check if capture_camera already executed by checking context.tool_results
            capture_already_done = any(
                tr['tool'] == 'capture_camera'
                for tr in context.tool_results
            )

            # Attempt fallback capture only if not already captured
            if wants_capture and not capture_already_done:
                logger.info(f"[{self.agent_id}] Attempting fallback image capture")
                self._fallback_capture(emit_fn, context)

            return {
                'success': False,
                'output': 'Maaf, model vision sedang tidak tersedia.',
                'tools_used': [],
                'context_updates': {},
                'error': str(e)
            }

    def _fallback_capture(self, emit_fn: Callable, context: TaskContext):
        """
        Automatically capture image without AI decision.
        Used as fallback when AI API fails.
        """
        try:
            # Execute capture_camera tool directly
            tool_result = self.agent_tools.execute('capture_camera', {})

            # Check if result is an image
            is_image_result = False
            result_data = None

            try:
                result_data = json.loads(tool_result)
                if isinstance(result_data, dict) and result_data.get('type') == 'image':
                    is_image_result = True
            except (json.JSONDecodeError, TypeError):
                pass

            # Regex fallback
            import re
            if not is_image_result and '/api/image/' in tool_result:
                json_match = re.search(r'\{.*?"type":\s*"image".*?\}', tool_result, re.DOTALL)
                if json_match:
                    try:
                        result_data = json.loads(json_match.group(0))
                        is_image_result = True
                    except:
                        pass

                if not is_image_result:
                    url_match = re.search(r'(/api/image/[\w\d_.-]+)', tool_result)
                    if url_match:
                        is_image_result = True
                        result_data = {
                            'type': 'image',
                            'url': url_match.group(1),
                            'description': 'Camera capture (fallback)',
                            'filename': url_match.group(1).split('/')[-1]
                        }

            # Emit image if detected
            if is_image_result and result_data:
                emit_fn('tool_image', {
                    'tool': 'capture_camera',
                    'image_url': result_data.get('url', ''),
                    'description': result_data.get('description', 'Kamera berhasil mengambil gambar'),
                    'width': result_data.get('width', 640),
                    'height': result_data.get('height', 480),
                    'filename': result_data.get('filename', ''),
                    'agent': self.agent_id,
                    'fallback': True  # Mark as fallback capture
                })
                logger.info(f"[{self.agent_id}] Fallback image emitted: {result_data.get('url')}")
                context.add_tool_result('capture_camera', tool_result)

                # Track image path
                if 'url' in result_data:
                    context.images_captured.append(result_data['url'])
            else:
                logger.warning(f"[{self.agent_id}] Fallback capture did not return image data")

        except Exception as e:
            logger.error(f"[{self.agent_id}] Fallback capture failed: {e}")


class SystemAgent(BaseAgent):
    """
    System Agent: OS commands, file operations, service management, system monitoring.
    Tools: run_command, read_file, write_file, list_directory, get_system_info, manage_service, get_processes
    """

    def __init__(self, ai_client: AIClient, agent_tools: AgentTools, socketio: SocketIO, config: AgentConfig):
        super().__init__('system', ai_client, agent_tools, socketio, config)


class MemoryAgent(BaseAgent):
    """
    Memory Agent: User facts, preferences, conversation history.
    Tools: save_memory, read_file (for reading memory.md)
    """

    def __init__(self, ai_client: AIClient, agent_tools: AgentTools, socketio: SocketIO, config: AgentConfig):
        super().__init__('memory', ai_client, agent_tools, socketio, config)


class PlannerAgent(BaseAgent):
    """
    Planner Agent: Complex multi-step tasks requiring coordination.
    Tools: All tools available.
    """

    def __init__(self, ai_client: AIClient, agent_tools: AgentTools, socketio: SocketIO, config: AgentConfig):
        super().__init__('planner', ai_client, agent_tools, socketio, config)


class LampAgent(BaseAgent):
    """
    Lamp Agent: Controls ESP32 lamps via MQTT.
    Handles natural language commands for turning lamps on/off/toggle in Bahasa Indonesia.
    """

    def __init__(self, ai_client, agent_tools, socketio, config):
        super().__init__("lamp", ai_client, agent_tools, socketio, config)

        # Override system prompt with lamp-specific one
        self.system_prompt = self._get_lamp_prompt()

    def _get_lamp_prompt(self):
        """Get the lamp agent system prompt."""
        return """You are a Lamp Agent for ElBot, specialized in controlling ESP32-connected lamps via MQTT.

Your capabilities:
- Turn lamps on/off/toggle using natural language commands in Bahasa Indonesia
- Check status of individual lamps or all lamps
- List all available lamps with their locations and aliases

Available tools:
- control_lamp: Turn a lamp on, off, or toggle. Requires lamp_name (e.g., 'ruang tamu', 'kamar') and action ('on', 'off', 'toggle').
- get_lamp_status: Get status of a specific lamp or all lamps. Optional lamp_name parameter; omit for all lamps.
- list_lamps: List all configured lamps with their names, locations, aliases, and current status.

IMPORTANT GUIDELINES:
1. Always respond in Bahasa Indonesia (Indonesian language).
2. When user asks to turn on/off a lamp, use control_lamp tool immediately.
3. When user asks about lamp status, use get_lamp_status tool.
4. When user asks what lamps are available, use list_lamps tool.
5. Lamp names in the config are in Indonesian (e.g., 'Ruang Tamu', 'Kamar Tidur', 'Dapur').
6. Always confirm actions after controlling lamps (e.g., "Lampu ruang tamu berhasil dinyalakan").
7. If a lamp name is not found, read the error message and suggest available lamps.
8. If the user's lamp name is ambiguous, use list_lamps to check and ask for clarification.
9. Be friendly and helpful in your responses.

Example interactions:
- User: "Nyalakan lampu ruang tamu" → control_lamp(lamp_name='ruang tamu', action='on')
- User: "Matikan lampu kamar" → control_lamp(lamp_name='kamar', action='off')
- User: "Lampu dapur nyala gak?" → get_lamp_status(lamp_name='dapur')
- User: "List lampu" or "ada lampu apa aja?" → list_lamps()
- User: "Tolong nyalakan semua lampu" → list_lamps() first, then control_lamp each with action='on'
"""

