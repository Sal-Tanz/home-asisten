import logging
import re
from typing import Callable, Awaitable

import edge_tts

from app.config import get_settings

logger = logging.getLogger(__name__)


class TTSService:
    """Text-to-Speech service using Microsoft Edge TTS."""

    def __init__(self):
        """Initialize TTS service."""
        settings = get_settings()
        self.voice = settings.tts_voice
        self.rate = settings.tts_rate
        self.volume = settings.tts_volume

    async def synthesize_stream(
        self,
        text: str,
        on_audio_chunk: Callable[[bytes], Awaitable[None]]
    ) -> None:
        """Stream synthesized audio chunks to callback.

        Args:
            text: Text to synthesize
            on_audio_chunk: Async callback receiving audio bytes for each chunk
        """
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume
            )

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    await on_audio_chunk(chunk["data"])

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            raise

    async def synthesize_to_bytes(self, text: str) -> bytes:
        """Synthesize text to complete audio bytes.

        Args:
            text: Text to synthesize

        Returns:
            Complete audio as bytes
        """
        chunks = []

        async def collect(data: bytes):
            chunks.append(data)

        await self.synthesize_stream(text, collect)
        return b''.join(chunks)

    def split_into_clauses(self, text: str) -> list[str]:
        """Split text into clauses on natural pause boundaries.

        Splits on sentence punctuation (.!?), commas, semicolons, colons
        followed by whitespace, and on newlines. Smaller clauses synthesize
        faster and each becomes a self-contained MP3 blob for reliable
        browser decoding.

        Args:
            text: Input text

        Returns:
            List of clause strings
        """
        clauses = re.split(r'(?<=[.!?,:;])\s+|\n+', text)
        return [clause for clause in clauses if clause.strip()]
