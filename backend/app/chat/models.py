from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any


@dataclass
class ChatMessage:
    """Represents a single chat message."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dict."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ChatSession:
    """Represents a chat session with message history."""
    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_message(self, role: str, content: str) -> ChatMessage:
        """Add a message to the session and update last_activity."""
        message = ChatMessage(role=role, content=content)
        self.messages.append(message)
        self.last_activity = datetime.now(timezone.utc)
        return message

    def get_messages_as_openai_format(self) -> List[Dict[str, str]]:
        """Convert messages to OpenAI format."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session for Socket.IO."""
        return {
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }
