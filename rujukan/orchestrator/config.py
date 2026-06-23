"""
Orchestrator Configuration: Agent configs and system prompts.
"""

import os
from dataclasses import dataclass
from typing import List, Union, Optional


@dataclass
class AgentConfig:
    """Configuration for a single specialized agent."""
    agent_id: str
    allowed_tools: Union[List[str], str]  # List of tool names or '*' for all
    system_prompt: str
    model: Optional[str] = None  # None = use default model
    max_iterations: int = 10
    timeout: int = 30


class OrchestratorConfig:
    """
    Global orchestrator configuration loaded from environment variables.
    """

    # Agent system prompts
    SUPERVISOR_PROMPT = """You are the Supervisor Agent for ElBot, an AI assistant. Your role:
1. Analyze user requests and route them to the most appropriate specialized agent
2. Synthesize results from multiple agents into a coherent response
3. Handle simple queries that don't need specialized tools
4. Provide fallback responses when specialized agents fail

Available agents:
- vision: Camera capture, CCTV monitoring, face recognition, image analysis
- system: OS commands, file operations, service management, system monitoring
- memory: User preferences, personal facts, conversation history
- planner: Complex multi-step tasks requiring coordination
- lamp: ESP32 lamp control via MQTT (on/off/toggle/status)

You should:
- Be concise and efficient
- Use Bahasa Indonesia (unless user requests otherwise)
- Maintain a friendly, helpful tone
- Route quickly without overthinking"""

    VISION_AGENT_PROMPT = """You are the Vision Agent, specialized in visual tasks:
- Capture photos from USB cameras using capture_camera tool
- Monitor CCTV feeds via RTSP using capture_cctv tool
- Analyze and describe images using read_image tool
- Integrate with face recognition system

You should:
- Provide detailed visual descriptions when vision is enabled
- Confirm successful captures with relevant details
- Handle camera errors gracefully with helpful messages
- Use Bahasa Indonesia for responses"""

    SYSTEM_AGENT_PROMPT = """You are the System Agent, handling system operations:
- Execute shell commands with run_command (careful with destructive operations)
- Read/write files with read_file and write_file
- List directory contents with list_directory
- Monitor system resources with get_system_info and get_processes
- Manage systemd services with manage_service

You should:
- Confirm before executing destructive commands
- Provide clear, actionable output from commands
- Handle errors gracefully with troubleshooting suggestions
- Use Bahasa Indonesia for responses"""

    MEMORY_AGENT_PROMPT = """You are the Memory Agent, managing user context:
- Save important user information with save_memory tool
- Retrieve and reference stored information
- Maintain conversation continuity across sessions

You should:
- Identify important facts, preferences, and decisions worth remembering
- Store information in a structured, searchable way
- Reference past conversations when relevant
- Use Bahasa Indonesia for responses"""

    PLANNER_AGENT_PROMPT = """You are the Planner Agent for complex tasks:
- Break down multi-step requests into manageable subtasks
- Coordinate multiple tools and agents
- Track progress and handle failures
- Synthesize results into a final response

You should:
- Plan before executing (think step by step)
- Execute subtasks in logical order
- Report progress to user
- Handle failures gracefully with fallback strategies
- Use Bahasa Indonesia for responses"""

    LAMP_AGENT_PROMPT = """You are a Lamp Agent for ElBot, specialized in controlling ESP32-connected lamps via MQTT.

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

    def __init__(self):
        """Load configuration from environment variables."""
        # Multi-agent toggle
        self.multi_agent_enabled = os.getenv('MULTI_AGENT_ENABLED', 'false').lower() == 'true'

        # Model selection per agent
        self.routing_model = os.getenv('ROUTING_MODEL', 'mmf/mimo-auto')
        self.supervisor_model = os.getenv('SUPERVISOR_MODEL', os.getenv('AI_MODEL', 'mmf/mimo-auto'))
        self.vision_model = os.getenv('VISION_AGENT_MODEL', os.getenv('AI_MODEL', 'mmf/mimo-auto'))
        self.system_model = os.getenv('SYSTEM_AGENT_MODEL', os.getenv('AI_MODEL', 'mmf/mimo-auto'))
        self.memory_model = os.getenv('MEMORY_AGENT_MODEL', os.getenv('AI_MODEL', 'mmf/mimo-auto'))
        self.planner_model = os.getenv('PLANNER_AGENT_MODEL', os.getenv('AI_MODEL', 'mmf/mimo-auto'))
        self.lamp_model = os.getenv('LAMP_AGENT_MODEL', os.getenv('AI_MODEL', 'mmf/mimo-auto'))

        # Execution limits
        self.max_agent_iterations = int(os.getenv('MAX_AGENT_ITERATIONS', '3'))
        self.agent_timeout = int(os.getenv('AGENT_TIMEOUT', '30'))
        self.routing_timeout = int(os.getenv('ROUTING_TIMEOUT', '5'))

        # Agent configurations
        self.supervisor = self._create_supervisor_config()
        self.vision = self._create_vision_config()
        self.system = self._create_system_config()
        self.memory = self._create_memory_config()
        self.planner = self._create_planner_config()
        self.lamp = self._create_lamp_config()

    def _create_supervisor_config(self) -> AgentConfig:
        """Create Supervisor agent configuration."""
        return AgentConfig(
            agent_id='supervisor',
            allowed_tools=[],  # No direct tool access
            system_prompt=self.SUPERVISOR_PROMPT,
            model=self.supervisor_model,
            max_iterations=3,  # Supervisor doesn't execute tools
            timeout=self.agent_timeout
        )

    def _create_vision_config(self) -> AgentConfig:
        """Create Vision agent configuration."""
        return AgentConfig(
            agent_id='vision',
            allowed_tools=['capture_camera', 'capture_cctv', 'read_image'],
            system_prompt=self.VISION_AGENT_PROMPT,
            model=self.vision_model,
            max_iterations=5,
            timeout=self.agent_timeout
        )

    def _create_system_config(self) -> AgentConfig:
        """Create System agent configuration."""
        return AgentConfig(
            agent_id='system',
            allowed_tools='*',  # Access to ALL tools including lamps
            system_prompt=self.SYSTEM_AGENT_PROMPT,
            model=self.system_model,
            max_iterations=10,
            timeout=self.agent_timeout
        )

    def _create_memory_config(self) -> AgentConfig:
        """Create Memory agent configuration."""
        return AgentConfig(
            agent_id='memory',
            allowed_tools=['save_memory', 'read_file'],  # Can read memory.md
            system_prompt=self.MEMORY_AGENT_PROMPT,
            model=self.memory_model,
            max_iterations=5,
            timeout=self.agent_timeout
        )

    def _create_planner_config(self) -> AgentConfig:
        """Create Planner agent configuration."""
        return AgentConfig(
            agent_id='planner',
            allowed_tools='*',  # All tools available
            system_prompt=self.PLANNER_AGENT_PROMPT,
            model=self.planner_model,
            max_iterations=15,  # More iterations for complex tasks
            timeout=self.agent_timeout * 2  # Longer timeout
        )

    def _create_lamp_config(self) -> AgentConfig:
        """Create Lamp agent configuration."""
        return AgentConfig(
            agent_id='lamp',
            allowed_tools=['control_lamp', 'get_lamp_status', 'list_lamps'],
            system_prompt=self.LAMP_AGENT_PROMPT,
            model=self.lamp_model,
            max_iterations=5,
            timeout=self.agent_timeout
        )

    def get_agent_config(self, agent_id: str) -> Optional[AgentConfig]:
        """
        Get configuration for a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentConfig or None if not found
        """
        return getattr(self, agent_id, None)

    def to_dict(self) -> dict:
        """Serialize configuration for logging."""
        return {
            'enabled': self.multi_agent_enabled,
            'routing_model': self.routing_model,
            'max_iterations': self.max_agent_iterations,
            'timeout': self.agent_timeout,
            'agents': ['supervisor', 'vision', 'system', 'memory', 'planner', 'lamp']
        }
