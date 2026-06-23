import requests
import json
import os
import logging
from typing import Iterator, Optional
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from agent_tools import TOOLS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


def _ensure_messages_endpoint(api_url):
    """Append /messages path segment if not already present."""
    if api_url.rstrip('/').endswith('/messages'):
        return api_url
    parsed = urlparse(api_url)
    path = parsed.path.rstrip('/')
    if path.endswith('/v1'):
        return urljoin(api_url + '/', 'messages')
    return urljoin(api_url + '/', 'v1/messages')


class AIClient:
    """Client for communicating with local AI API"""

    def __init__(self):
        self.api_url = os.getenv('AI_API_URL', 'http://localhost:11434/api/generate')
        self.model = os.getenv('AI_MODEL', 'llama2')
        self.api_key = os.getenv('AI_API_KEY')
        self.routing_model = os.getenv('ROUTING_MODEL', self.model)

        # HTTP connection pooling for persistent connections (reduces latency ~100-300ms per call)
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})
        if self.api_key:
            self._session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'x-api-key': self.api_key
            })

        logger.info(f"AI Client initialized - URL: {self.api_url}, Model: {self.model}")

    def test_connection(self) -> tuple[bool, str]:
        """
        Test connection to AI API

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            logger.info(f"Testing connection to {self.api_url}")

            # Try a simple request
            headers = {'Content-Type': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            # For Anthropic/Claude API, we need to use chat endpoint
            if 'anthropic' in self.api_url or 'claude' in self.api_url or 'hidepulsa' in self.api_url:
                test_url = _ensure_messages_endpoint(self.api_url)
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 10
                }
            else:
                # For Ollama or similar
                test_url = self.api_url.rstrip('/') + '/chat/completions'
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": False
                }

            logger.info(f"Sending test request to {test_url}")
            response = self._session.post(
                test_url,
                json=payload,
                headers=headers,
                timeout=10
            )

            logger.info(f"Response status: {response.status_code}")

            if response.status_code == 200:
                logger.info("Connection test successful")
                return True, "Connected successfully!"
            else:
                error_msg = f"API returned status {response.status_code}: {response.text[:200]}"
                logger.error(error_msg)
                return False, error_msg

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection failed: Cannot reach {self.api_url}"
            logger.error(f"{error_msg} - {str(e)}")
            return False, error_msg
        except requests.exceptions.Timeout:
            error_msg = "Connection timeout"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(f"Connection test failed: {error_msg}")
            return False, error_msg

    def chat_stream(self, message: str, conversation_history: Optional[list] = None) -> Iterator[str]:
        """
        Send message to AI and stream the response

        Args:
            message: User message to send
            conversation_history: List of previous messages for context

        Yields:
            Chunks of AI response text
        """
        logger.info(f"Sending message to AI: {message[:50]}...")

        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        try:
            # Check if using Anthropic/Claude API format
            if 'anthropic' in self.api_url or 'claude' in self.api_url or 'hidepulsa' in self.api_url:
                yield from self._chat_stream_anthropic(message, conversation_history, headers)
            else:
                yield from self._chat_stream_ollama(message, conversation_history, headers)

        except requests.exceptions.RequestException as e:
            error_msg = f"\n[Error: {str(e)}]"
            logger.error(f"Request failed: {error_msg}")
            yield error_msg

    def _chat_stream_anthropic(self, message: str, conversation_history: Optional[list], headers: dict) -> Iterator[str]:
        """Stream chat for Anthropic/Claude API"""
        # Build messages array
        messages = []
        if conversation_history:
            for msg in conversation_history[-10:]:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "stream": True
        }

        logger.info(f"Sending Anthropic API request to {self.api_url}/messages")

        api_url = _ensure_messages_endpoint(self.api_url)

        response = self._session.post(
            api_url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=60
        )

        logger.info(f"Response status: {response.status_code}")
        response.raise_for_status()

        # Stream the response
        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode('utf-8')
            if not line_str.startswith('data: '):
                continue
            line_str = line_str[6:]  # Remove 'data: ' prefix
            if line_str == '[DONE]':
                break

            try:
                data = json.loads(line_str)
                if data.get('type') == 'content_block_delta':
                    delta = data.get('delta', {})
                    if 'text' in delta:
                        yield delta['text']
                elif data.get('type') == 'message_delta':
                    logger.info("Message stream completed")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode JSON: {line_str[:100]}")
                continue

    def _chat_stream_ollama(self, message: str, conversation_history: Optional[list], headers: dict) -> Iterator[str]:
        """Stream chat for Ollama API"""
        prompt = self._build_prompt(message, conversation_history)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True
        }

        logger.info(f"Sending Ollama API request to {self.api_url}")

        response = self._session.post(
            self.api_url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=60
        )

        logger.info(f"Response status: {response.status_code}")
        response.raise_for_status()

        # Stream the response
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if 'response' in data:
                        yield data['response']

                    # Check if generation is done
                    if data.get('done', False):
                        logger.info("Response stream completed")
                        break
                except json.JSONDecodeError:
                    continue

    def _build_prompt(self, message: str, conversation_history: Optional[list] = None) -> str:
        """Build prompt with conversation context"""
        if not conversation_history:
            return message

        # Format conversation history
        prompt_parts = []
        for msg in conversation_history[-10:]:  # Keep last 10 messages for context
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt_parts.append(f"{role.capitalize()}: {content}")

        prompt_parts.append(f"User: {message}")
        prompt_parts.append("Assistant:")

        return "\n".join(prompt_parts)

    def chat_stream_with_tools(self, messages: list, tools: Optional[list] = None, model: Optional[str] = None, max_tokens: Optional[int] = None) -> Iterator[dict]:
        """
        Send conversation to AI with tools and stream structured responses.

        Args:
            messages: List of message dicts with role/content (Anthropic format)
            tools: Optional list of tool definitions. If None, uses all TOOLS.
            model: Optional model name. If None, uses self.model.
            max_tokens: Optional max_tokens override. If None, auto-detects based on context.

        Yields:
            dicts: {'type': 'text', 'content': '...'}
                    {'type': 'tool_use', 'id': '...', 'name': '...', 'input': {...}}
                    {'type': 'message_stop'}
        """
        headers = {
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01',
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            headers['x-api-key'] = self.api_key

        api_url = _ensure_messages_endpoint(self.api_url)

        # Use provided tools or default to all TOOLS
        tools_to_use = tools if tools is not None else TOOLS

        # Use provided model or default to self.model
        model_to_use = model if model is not None else self.model

        # Filter out 'system' role messages — Anthropic Messages API only supports 'user' and 'assistant'
        filtered_messages = [
            msg for msg in messages
            if msg.get('role') in ('user', 'assistant')
        ]

        # Dynamic max_tokens based on context (optimization: reduce token generation overhead)
        if max_tokens is None:
            # Routing calls: very small response needed (~50 tokens)
            if tools is None or len(tools) == 0:
                max_tokens = 512
            # Tool-use calls: moderate response (most responses <2048 tokens)
            else:
                max_tokens = 2048

        payload = {
            "model": model_to_use,
            "messages": filtered_messages,
            "max_tokens": max_tokens,
            "stream": True,
            "tools": tools_to_use
        }

        logger.info(f"Sending tool-use request to {api_url} with model {model_to_use}, {len(tools_to_use)} tools, max_tokens={max_tokens}, {len(filtered_messages)} messages (filtered from {len(messages)})")
        logger.info(f"Messages count: {len(messages)}, last role: {messages[-1].get('role') if messages else 'none'}")

        response = self._session.post(
            api_url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=(10, 90)
        )

        logger.info(f"Tool-use response status: {response.status_code}")
        if response.status_code >= 400:
            error_body = ""
            try:
                error_body = response.text[:500]
            except:
                pass
            logger.error(f"AI API error {response.status_code}: {error_body}")
            response.raise_for_status()
        else:
            response.raise_for_status()

        current_block_type = None
        current_tool_id = None
        current_tool_name = None
        current_tool_input = ""

        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode('utf-8')

            # Skip non-data lines (event: headers, empty comments)
            if not line_str.startswith('data: '):
                continue

            line_str = line_str[6:]  # Remove 'data: ' prefix

            if line_str == '[DONE]':
                break

            try:
                data = json.loads(line_str)
                event_type = data.get('type', '')

                if event_type == 'content_block_start':
                    block = data.get('content_block', {})
                    current_block_type = block.get('type')
                    if current_block_type == 'tool_use':
                        current_tool_id = block.get('id', '')
                        current_tool_name = block.get('name', '')
                        current_tool_input = ''

                elif event_type == 'content_block_delta':
                    delta = data.get('delta', {})
                    delta_type = delta.get('type', '')

                    if delta_type == 'text_delta':
                        yield {'type': 'text', 'content': delta.get('text', '')}
                    elif delta_type == 'input_json_delta':
                        current_tool_input += delta.get('partial_json', '')
                    elif delta_type == 'thinking_delta':
                        pass  # Extended thinking content — ignore silently

                elif event_type == 'content_block_stop':
                    if current_block_type == 'tool_use' and current_tool_id:
                        if current_tool_input.strip():
                            try:
                                tool_input = json.loads(current_tool_input)
                            except json.JSONDecodeError:
                                tool_input = {'raw': current_tool_input}
                        else:
                            tool_input = {}

                        yield {
                            'type': 'tool_use',
                            'id': current_tool_id,
                            'name': current_tool_name,
                            'input': tool_input
                        }

                    # Always reset block state (handles thinking blocks, text blocks, etc.)
                    current_block_type = None
                    current_tool_id = None
                    current_tool_name = None
                    current_tool_input = ''

                elif event_type == 'message_stop':
                    logger.info("Message stream completed")
                    yield {'type': 'message_stop'}

                elif event_type == 'message_delta':
                    pass  # Final metadata, ignore

            except json.JSONDecodeError:
                logger.warning(f"Failed to decode: {line_str[:100]}")
                continue
