"""
Multi-Agent Orchestr for ElBot
Coordinates specialized agents (Vision, System, Memory, Planner) under a Supervisor.
"""

from .orchestrator import AgentOrchestrator
from .config import OrchestratorConfig
from .task_context import TaskContext

__all__ = ['AgentOrchestrator', 'OrchestratorConfig', 'TaskContext']
