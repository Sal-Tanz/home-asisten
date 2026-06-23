"""AI Agent using OpenAI-compatible API with streaming and tool support."""

import json
from typing import List, Dict, Any, Callable, Optional
from openai import AsyncOpenAI

from app.config import get_settings


class AIAgent:
    """AI Agent for handling chat completions with streaming and tool execution."""

    def __init__(self):
        """Initialize AI Agent with custom OpenAI-compatible endpoint."""
        settings = get_settings()
        self.client = AsyncOpenAI(
            base_url=settings.ai_api_base_url,
            api_key=settings.ai_api_key,
            timeout=90.0,  # read timeout — prevents hangs on slow proxy responses
            default_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        self.model = settings.ai_model_name

    async def stream_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        on_text_chunk: Callable[[str], Any],
        on_tool_call: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """
        Stream chat completion with a robust tool-calling loop.

        Standard OpenAI tool-calling round-trip with hardening for proxies/models
        that behave unpredictably (missing tc.index, truncated responses, empty
        turns, tool-execution exceptions):
        1. Stream a completion. Text deltas go to on_text_chunk.
        2. If the model called tool(s), execute each (errors become tool results
           so the model can recover gracefully), append assistant tool_calls +
           tool result messages, then loop back for a final reply.
        3. Repeat until the model emits a turn with no tool calls, or until
           MAX_ITERATIONS. If the loop ends with no text, emit a fallback reply
           so the user is never left in silence.
        """
        MAX_ITERATIONS = 10  # cap; complex commands legitimately need 3-4 turns
        any_tool_ran = False  # track whether we ever executed a tool

        for _ in range(MAX_ITERATIONS):
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                stream=True
            )

            # Accumulate assistant deltas for this turn
            assistant_text = ""
            tool_calls = {}     # normalized index -> {id, name, arguments}
            finish_reason = None
            next_auto_index = 0  # for normalizing missing tc.index values

            async for chunk in stream:
                choices = chunk.choices
                # Some OpenAI-compatible proxies send a final usage-only chunk
                # with empty choices; guard against IndexError.
                if not choices:
                    continue

                delta = choices[0].delta
                if not delta:
                    continue

                # Stream text content
                if delta.content:
                    assistant_text += delta.content
                    await on_text_chunk(delta.content)

                # Accumulate tool-call deltas (may span multiple chunks).
                # Robust index normalization handles proxies that omit tc.index:
                #   - index present      → use it directly (standard OpenAI)
                #   - index None + id    → start of a NEW tool call → fresh index
                #   - index None, no id  → arguments continuation → last tool call
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.index is not None:
                            raw_index = tc.index
                        elif tc.id:
                            # A new tool call started without an index.
                            raw_index = next_auto_index
                        else:
                            # Continuation (arguments) — attach to the most
                            # recent tool call, or index 0 if none yet.
                            raw_index = max(tool_calls) if tool_calls else 0

                        if raw_index not in tool_calls:
                            next_auto_index = max(next_auto_index, raw_index + 1)

                        entry = tool_calls.setdefault(raw_index, {
                            "id": None,
                            "name": None,
                            "arguments": ""
                        })
                        if tc.id:
                            entry["id"] = tc.id
                        if tc.function and tc.function.name:
                            entry["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            entry["arguments"] += tc.function.arguments

                # Track finish reason for truncation detection (Fix #4)
                if choices[0].finish_reason:
                    finish_reason = choices[0].finish_reason

            # If the model didn't call any tools this turn, this is the final
            # text answer (even if empty). Done.
            if not tool_calls:
                # Empty turn with no prior tool and no text → guard (Fix #5)
                if not assistant_text and not any_tool_ran:
                    await on_text_chunk(
                        "Maaf, saya tidak bisa memproses permintaan itu. Coba lagi."
                    )
                return

            # Warn on truncated tool-call args so it's debuggable (Fix #4)
            if finish_reason == "length":
                import logging
                logging.getLogger(__name__).warning(
                    "AI response truncated (finish_reason=length); "
                    "tool-call arguments may be incomplete"
                )

            # Build the assistant message carrying the tool_calls (Fix context).
            # If the proxy omitted a tool-call id, assign a synthetic one so the
            # assistant tool_calls and tool-result messages stay paired (required
            # by the OpenAI API format).
            assistant_tool_calls = []
            for idx in sorted(tool_calls):
                tc = tool_calls[idx]
                if not tc["id"]:
                    tc["id"] = f"call_{idx}"
                assistant_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"] or "unknown",
                        "arguments": tc["arguments"] or "{}",
                    }
                })
            messages.append({
                "role": "assistant",
                "content": assistant_text or None,
                "tool_calls": assistant_tool_calls,
            })

            # Execute each tool, capturing exceptions as error results (Fix #3)
            # so the model can apologize/recover instead of aborting the reply.
            for idx in sorted(tool_calls):
                tc = tool_calls[idx]
                # Parse arguments (fallback to {} if malformed/truncated)
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}

                try:
                    result = await on_tool_call({
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": args,
                    })
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(
                        f"Tool execution error ({tc['name']}): {e}", exc_info=True
                    )
                    result = {"error": f"Tool execution failed: {e}"}

                any_tool_ran = True
                # The tool result must be fed back so the model can reply.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result) if result is not None else "{}",
                })

            # Loop back: request another completion so the model can produce its
            # natural-language reply using the tool results just appended.

        # Loop exhausted (MAX_ITERATIONS) without a final text reply (Fix #1).
        # Emit a fallback so the user is never left in silence.
        await on_text_chunk(
            "Maaf, permintaan itu terlalu kompleks untuk saya proses. Coba sederhanakan."
        )

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
