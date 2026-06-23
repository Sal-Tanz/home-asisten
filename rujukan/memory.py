import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
MEMORY_FILE = os.path.join(os.path.dirname(__file__), 'memory.md')
INSTRUCTIONS_FILE = os.path.join(os.path.dirname(__file__), 'instructions.md')


def load_memory(max_chars=4000):
    """Load personality/user memory from memory.md, truncated to max_chars"""
    if not os.path.exists(MEMORY_FILE):
        return ""
    with open(MEMORY_FILE, 'r') as f:
        content = f.read()
    if len(content) > max_chars:
        content = content[-max_chars:]
        idx = content.find('\n')
        if idx > 0:
            content = content[idx + 1:]
    return content.strip()


def load_instructions(max_chars=2000):
    """Load AI instructions from instructions.md, truncated to max_chars"""
    if not os.path.exists(INSTRUCTIONS_FILE):
        return ""
    with open(INSTRUCTIONS_FILE, 'r') as f:
        content = f.read()
    if len(content) > max_chars:
        content = content[:max_chars]
        # Find last newline to avoid cutting mid-sentence
        idx = content.rfind('\n')
        if idx > 0:
            content = content[:idx]
    return content.strip()


def save_memory_entry(topic, content):
    """Append a new memory entry to memory.md"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"\n\n## [{timestamp}] {topic}\n{content}"
    with open(MEMORY_FILE, 'a') as f:
        f.write(entry)
    logger.info(f"Memory saved: {topic[:60]}")
    return f"OK: Saved memory entry '{topic}' ({len(content)} chars)"