"""AI Agent using OpenAI-compatible API with streaming and tool support."""

import json
from typing import List, Dict, Any, Callable, Optional
from openai import AsyncOpenAI


class AIAgent:
    """AI Agent for handling chat completions with streaming and tool execution."""

    def __init__(self):
        """Initialize AI Agent with custom OpenAI-compatible endpoint."""
        self.client = AsyncOpenAI(
            base_url="https://api-ai.elektrounsub.com/v1",
            api_key="sk-f86cd6ad61e2754f-tb3cn0-8412a37b"
        )
        self.model = "mmf/mimo-auto"

    async def stream_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        on_text_chunk: Callable[[str], Any],
        on_tool_call: Callable[[Dict[str, Any]], Any]
    ) -> Optional[Any]:
        """
        Stream chat completion with tool support and immediate execution.

        Args:
            messages: List of chat messages in OpenAI format
            tools: List of tool definitions in OpenAI format
            on_text_chunk: Async callback for text chunks (receives content string)
            on_tool_call: Async callback for tool calls (receives dict with id, name, args)
                         Should return result if tool execution completes the stream

        Returns:
            Result from on_tool_call if a tool was executed, None otherwise
        """
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=True
        )

        current_tool_call = None

        async for chunk in stream:
            # Extract delta from chunk
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Handle text content streaming
            if delta.content:
                await on_text_chunk(delta.content)

            # Handle tool calls streaming
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    # Only handle the first tool call (index 0)
                    if tc.index == 0:
                        # New tool call starting
                        if tc.id:
                            # If we have a previous tool call, execute it first
                            if current_tool_call:
                                result = await on_tool_call(current_tool_call)
                                if result:
                                    return result

                            # Initialize new tool call
                            current_tool_call = {
                                "id": tc.id,
                                "name": tc.function.name,
                                "args": ""
                            }

                        # Accumulate function arguments
                        if tc.function.arguments:
                            current_tool_call["args"] += tc.function.arguments

            # Check if stream finished with tool calls
            if chunk.choices[0].finish_reason == "tool_calls":
                if current_tool_call:
                    # Parse accumulated JSON arguments
                    try:
                        current_tool_call["args"] = json.loads(current_tool_call["args"])
                    except json.JSONDecodeError:
                        # If args failed to parse, keep as string
                        pass

                    # Execute the final tool call
                    result = await on_tool_call(current_tool_call)
                    return result

        return None

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> str:
        """
        Simple non-streaming chat completion.

        Args:
            messages: List of chat messages in OpenAI format
            **kwargs: Additional parameters to pass to the API

        Returns:
            The assistant's response content as a string
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False,
            **kwargs
        )

        return response.choices[0].message.content
