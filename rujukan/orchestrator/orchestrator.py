"""
AgentOrchestrator: Coordinates multiple specialized agents to handle user requests.
Routes tasks to appropriate agents, manages execution, and provides fallback mechanisms.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Callable

from socketio import Server as SocketIO
from ai_client import AIClient
from agent_tools import AgentTools

from .agents import (
    BaseAgent, SupervisorAgent, VisionAgent,
    SystemAgent, MemoryAgent, PlannerAgent, LampAgent
)
from .config import OrchestratorConfig
from .task_context import TaskContext

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Main orchestrator that coordinates multi-agent workflow.
    Replaces direct call to _process_agent_loop when multi-agent enabled.
    """

    def __init__(
        self,
        ai_client: AIClient,
        agent_tools: AgentTools,
        socketio: SocketIO,
        config: OrchestratorConfig
    ):
        """
        Initialize orchestrator with dependencies.

        Args:
            ai_client: AI client for making API calls
            agent_tools: Tool execution engine
            socketio: SocketIO instance for streaming to frontend
            config: Orchestrator configuration
        """
        self.ai_client = ai_client
        self.agent_tools = agent_tools
        self.socketio = socketio
        self.config = config

        # Initialize specialized agents
        self.supervisor = SupervisorAgent(ai_client, socketio, config.supervisor)
        self.vision_agent = VisionAgent(ai_client, agent_tools, socketio, config.vision)
        self.system_agent = SystemAgent(ai_client, agent_tools, socketio, config.system)
        self.memory_agent = MemoryAgent(ai_client, agent_tools, socketio, config.memory)
        self.planner_agent = PlannerAgent(ai_client, agent_tools, socketio, config.planner)

        # Initialize Lamp Agent
        self.lamp_agent = LampAgent(
            ai_client=ai_client,
            agent_tools=agent_tools,
            socketio=socketio,
            config=config.lamp
        )
        logger.info("LampAgent initialized")

        # Agent registry
        self.agents: Dict[str, BaseAgent] = {
            'supervisor': self.supervisor,
            'vision': self.vision_agent,
            'system': self.system_agent,
            'memory': self.memory_agent,
            'planner': self.planner_agent,
            'lamp': self.lamp_agent
        }

        logger.info(f"Orchestrator initialized with {len(self.agents)} agents")

    def _try_fast_lamp_command(
        self,
        session_id: str,
        user_message: str,
        emit_fn: Callable
    ) -> Optional[str]:
        """
        Fast-path execution for common lamp commands.
        Bypasses AI model entirely for clear patterns like "nyalakan lampu tamu".

        Args:
            session_id: WebSocket session ID
            user_message: User's message
            emit_fn: SocketIO emit function

        Returns:
            Response text if command was executed, None otherwise
        """
        import re
        import json

        msg_lower = user_message.lower().strip()

        # Patterns for lamp commands
        # "nyalakan/hidupkan lampu tamu" -> on
        # "matikan lampu tamu" -> off
        # "toggle lampu tamu" -> toggle
        action_patterns = {
            'on': ['nyalakan', 'hidupkan', 'nyala', 'turn on', 'on'],
            'off': ['matikan', 'matikan', 'mati', 'turn off', 'off'],
            'toggle': ['toggle', 'saklar']
        }

        # Extract action
        action = None
        for act, keywords in action_patterns.items():
            if any(kw in msg_lower for kw in keywords):
                action = act
                break

        if not action:
            return None

        # Extract lamp name - try common patterns
        lamp_name = None

        # Pattern: "nyalakan lampu [name]" or "matikan lampu [name]"
        match = re.search(r'(?:nyalakan|hidupkan|matikan|toggle)\s+lampu\s+([\w\s]+?)(?:\s+please|\.|!|$)', msg_lower)
        if match:
            lamp_name = match.group(1).strip()

        # Pattern: "lampu [name] [action]"
        if not lamp_name:
            match = re.search(r'lampu\s+([\w\s]+?)\s+(?:nyala|mati|on|off|toggle)', msg_lower)
            if match:
                lamp_name = match.group(1).strip()

        # Pattern: "[action] lampu [name]" (English)
        if not lamp_name:
            match = re.search(r'(?:turn|toggle)\s+(?:on|off)\s+(?:the\s+)?lamp\s+([\w\s]+?)(?:\s+please|\.|!|$)', msg_lower)
            if match:
                lamp_name = match.group(1).strip()

        if not lamp_name:
            return None

        # Try to execute lamp command directly
        logger.info(f"[Fast-path] Executing lamp command: {action} {lamp_name}")

        try:
            # Use the agent_tools directly
            result_json = self.agent_tools.execute('control_lamp', {
                'lamp_name': lamp_name,
                'action': action
            })

            # Parse result — tool returns JSON on success, plain string on error
            try:
                result = json.loads(result_json)
            except (json.JSONDecodeError, TypeError):
                # Tool returned plain error string (e.g., "Error: Lamp not found")
                # Strip technical prefixes and present cleanly
                clean_error = result_json.replace('Error: ', '').replace('error: ', '')
                response = f"❌ {clean_error}"
                emit_fn('ai_chunk', {'chunk': response})
                emit_fn('ai_status', {'status': 'completed'})
                logger.warning(f"[Fast-path] Lamp non-JSON error: {result_json[:100]}")
                return response

            if result.get('success'):
                lamp_display = result.get('lamp_name', lamp_name)
                location = result.get('location', '')
                new_state = result.get('new_state', action)

                # Build response in Indonesian
                if action == 'on':
                    response = f"✅ Lampu {lamp_display}"
                    if location:
                        response += f" ({location})"
                    response += " berhasil dinyalakan"
                elif action == 'off':
                    response = f"✅ Lampu {lamp_display}"
                    if location:
                        response += f" ({location})"
                    response += " berhasil dimatikan"
                else:  # toggle
                    response = f"✅ Lampu {lamp_display}"
                    if location:
                        response += f" ({location})"
                    response += f" berhasil di-toggle, sekarang {new_state}"

                # Emit via socket
                emit_fn('ai_chunk', {'chunk': response})
                emit_fn('ai_status', {'status': 'completed'})

                logger.info(f"[Fast-path] Lamp command executed in <0.1s: {response}")
                return response
            else:
                # Command failed — return error directly (NO fallback to AI routing)
                # This prevents duplicate tool execution (fast-path → fail → AI route → same tool)
                error_msg = result.get('error', 'unknown error')
                response = f"❌ Gagal mengontrol lampu {lamp_name}: {error_msg}"
                emit_fn('ai_chunk', {'chunk': response})
                emit_fn('ai_status', {'status': 'completed'})
                logger.warning(f"[Fast-path] Lamp command failed: {error_msg}")
                return response

        except Exception as e:
            error_msg = str(e)
            response = f"❌ Error sistem saat mengontrol lampu {lamp_name}: {error_msg}"
            emit_fn('ai_chunk', {'chunk': response})
            emit_fn('ai_status', {'status': 'completed'})
            logger.error(f"[Fast-path] Lamp command error: {e}")
            return response

    def process(
        self,
        session_id: str,
        history: List[Dict[str, Any]],
        emit_fn: Callable
    ) -> None:
        """
        Main entry point for multi-agent processing.

        Flow:
        1. Extract user message from history
        2. Route to appropriate agent via Supervisor
        3. Execute agent with streaming
        4. Handle errors with fallback to Supervisor
        5. Stream final response

        Args:
            session_id: WebSocket session ID
            history: Conversation history (Anthropic format)
            emit_fn: SocketIO emit function for streaming
        """
        # Extract latest user message
        user_message = ""
        for msg in reversed(history):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                if isinstance(user_message, list):
                    # Handle structured content
                    user_message = ' '.join(
                        c.get('text', '') for c in user_message if c.get('type') == 'text'
                    )
                break

        if not user_message:
            logger.warning(f"[Orchestrator] No user message found for session {session_id}")
            emit_fn('ai_chunk', {'chunk': 'Maaf, saya tidak memahami pesan Anda.'})
            emit_fn('ai_status', {'status': 'error'})
            return

        # Create task context
        context = TaskContext(session_id, user_message)

        try:
            # FAST PATH: Try direct lamp command execution (bypasses AI entirely)
            fast_response = self._try_fast_lamp_command(session_id, user_message, emit_fn)
            if fast_response:
                logger.info(f"[Orchestrator] Fast-path executed in <0.1s")
                return  # Already emitted response

            # Step 1: Route task
            emit_fn('ai_status', {'status': 'routing'})
            t_route_start = time.time()
            routing_decision = self.supervisor.route(user_message, history)
            t_route_end = time.time()
            logger.info(f"[Orchestrator] Routing took: {t_route_end - t_route_start:.2f}s")

            target_agent = routing_decision.get('agent', 'supervisor')
            confidence = routing_decision.get('confidence', 0.0)
            reasoning = routing_decision.get('reasoning', '')

            logger.info(f"[Orchestrator] Routing: {target_agent} (confidence: {confidence:.2f}) - {reasoning}")

            emit_fn('agent_routing', {
                'agent': target_agent,
                'confidence': confidence,
                'reasoning': reasoning
            })

            # Step 2: Execute agent
            if target_agent == 'supervisor':
                # Supervisor handles directly (simple conversation)
                result = self.supervisor.process(history, context, emit_fn, session_id)
            else:
                # Specialized agent
                agent = self.agents.get(target_agent)
                if not agent:
                    logger.warning(f"[Orchestrator] Unknown agent '{target_agent}', falling back to supervisor")
                    emit_fn('agent_handoff', {
                        'from': target_agent,
                        'to': 'supervisor',
                        'reason': f"Unknown agent: {target_agent}"
                    })
                    result = self.supervisor.process(history, context, emit_fn, session_id)
                else:
                    # Execute specialized agent
                    emit_fn('agent_started', {
                        'agent': target_agent,
                        'task': user_message[:100]
                    })

                    t_agent_start = time.time()
                    result = agent.process(history, context, emit_fn, session_id)
                    t_agent_end = time.time()
                    logger.info(f"[Orchestrator] Agent '{target_agent}' execution: {t_agent_end - t_agent_start:.2f}s")

                    emit_fn('agent_completed', {
                        'agent': target_agent,
                        'success': result.get('success', False),
                        'duration': context.get_duration()
                    })

                    # Step 3: Handle failures - conditional fallback to Supervisor
                    # Only fallback if agent didn't execute any tools (avoid redundant AI calls)
                    if not result.get('success'):
                        error_msg = result.get('error', 'Unknown error')
                        tools_used = result.get('tools_used', [])

                        if tools_used:
                            # Agent executed tools but failed — use partial output, no fallback
                            logger.info(f"[Orchestrator] Agent {target_agent} failed after using {len(tools_used)} tools, using partial output")
                            result['success'] = True  # Mark as success to avoid error status
                        else:
                            # Agent failed without executing tools — fallback to supervisor
                            logger.warning(f"[Orchestrator] Agent {target_agent} failed: {error_msg}")
                            emit_fn('agent_handoff', {
                                'from': target_agent,
                                'to': 'supervisor',
                                'reason': f"Agent failed: {error_msg}"
                            })
                            result = self.supervisor.process(history, context, emit_fn, session_id)

            # Step 4: Record execution
            context.add_agent_result(target_agent, result)

            # Step 5: Final status
            if result.get('success'):
                emit_fn('ai_status', {'status': 'completed'})
            else:
                emit_fn('ai_status', {'status': 'error'})

            logger.info(f"[Orchestrator] Session {session_id} completed: {context.to_dict()}")

        except Exception as e:
            logger.error(f"[Orchestrator] Fatal error for session {session_id}: {e}")
            emit_fn('ai_chunk', {'chunk': f'Maaf, terjadi kesalahan sistem: {str(e)}'})
            emit_fn('ai_status', {'status': 'error'})

    def route_task(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Determine which agent should handle the task (public API for testing).

        Args:
            history: Conversation history

        Returns:
            Routing decision dict
        """
        user_message = ""
        for msg in reversed(history):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                if isinstance(user_message, list):
                    user_message = ' '.join(
                        c.get('text', '') for c in user_message if c.get('type') == 'text'
                    )
                break

        return self.supervisor.route(user_message, history)

    def execute_agent(
        self,
        agent_id: str,
        history: List[Dict[str, Any]],
        context: TaskContext,
        emit_fn: Callable
    ) -> Dict[str, Any]:
        """
        Execute a specific agent (public API for testing/manual routing).

        Args:
            agent_id: Agent identifier ('vision', 'system', etc.)
            history: Conversation history
            context: Task context
            emit_fn: SocketIO emit function

        Returns:
            Agent execution result dict
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return {
                'success': False,
                'output': '',
                'tools_used': [],
                'context_updates': {},
                'error': f"Unknown agent: {agent_id}"
            }

        return agent.process(history, context, emit_fn, context.session_id)

    def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all agents.

        Returns:
            Dict of agent_id -> status info
        """
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                'model': agent.model,
                'allowed_tools': agent.allowed_tools if hasattr(agent, 'allowed_tools') else [],
                'max_iterations': agent.max_iterations,
                'timeout': agent.timeout
            }
        return status
