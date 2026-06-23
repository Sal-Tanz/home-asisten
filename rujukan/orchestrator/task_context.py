"""
TaskContext: Shared state across agents in a single request.
Tracks execution, tool results, and inter-agent communication.
"""

import time
from typing import Dict, List, Any, Optional


class TaskContext:
    """
    Shared context that passes through all agents during a single user request.
    Agents can store/retrieve data to coordinate and avoid redundant work.
    """

    def __init__(self, session_id: str, initial_message: str):
        """
        Initialize task context for a request.

        Args:
            session_id: WebSocket session ID
            initial_message: User's original message
        """
        self.session_id = session_id
        self.initial_message = initial_message
        self.current_agent: Optional[str] = None
        self.agents_executed: List[Dict[str, Any]] = []
        self.shared_data: Dict[str, Any] = {}  # Inter-agent communication
        self.tool_results: List[Dict[str, Any]] = []
        self.images_captured: List[str] = []
        self.errors: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def add_agent_result(self, agent_id: str, result: Dict[str, Any]) -> None:
        """
        Store result from an agent execution.

        Args:
            agent_id: Agent identifier (e.g., 'vision', 'system')
            result: Agent's execution result dict
        """
        self.agents_executed.append({
            'agent_id': agent_id,
            'result': result,
            'timestamp': time.time()
        })

        # Track images if Vision Agent captured any
        if agent_id == 'vision' and 'image_path' in result:
            self.images_captured.append(result['image_path'])

    def get_agent_result(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve result from a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent's result dict, or None if not found
        """
        for item in reversed(self.agents_executed):
            if item['agent_id'] == agent_id:
                return item['result']
        return None

    def get_last_agent_result(self) -> Optional[Dict[str, Any]]:
        """
        Get result from most recently executed agent.

        Returns:
            Last agent's result dict, or None if no agents executed
        """
        if self.agents_executed:
            return self.agents_executed[-1]['result']
        return None

    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """
        Track a tool execution result.

        Args:
            tool_name: Name of the tool executed
            result: Tool's return value
        """
        self.tool_results.append({
            'tool': tool_name,
            'result': result,
            'timestamp': time.time()
        })

    def add_error(self, agent_id: str, error: str) -> None:
        """
        Record an error from an agent.

        Args:
            agent_id: Agent that encountered the error
            error: Error message
        """
        self.errors.append({
            'agent': agent_id,
            'error': error,
            'timestamp': time.time()
        })

    def get_duration(self) -> float:
        """
        Get total execution duration in seconds.

        Returns:
            Seconds since context creation
        """
        return time.time() - self.start_time

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize context for logging/debugging.

        Returns:
            Dict representation of context state
        """
        return {
            'session_id': self.session_id,
            'initial_message': self.initial_message[:100],
            'current_agent': self.current_agent,
            'agents_executed': [a['agent_id'] for a in self.agents_executed],
            'tool_count': len(self.tool_results),
            'image_count': len(self.images_captured),
            'error_count': len(self.errors),
            'duration_seconds': round(self.get_duration(), 2)
        }

    def __repr__(self) -> str:
        return f"TaskContext(session={self.session_id}, agents={len(self.agents_executed)}, errors={len(self.errors)})"
