import asyncio
import json
import logging
import subprocess
from typing import Optional

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)

# Persistent HTTP session (connection pooling)
_stt_session = requests.Session()
_stt_session.headers.update({
    'User-Agent': 'Mozilla/5.0',
    'Content-Type': 'audio/x-flac; rate=16000',
})


class STTService:
    """Speech-to-Text service using Google Speech API v2."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.google_stt_key
        self.api_url = settings.google_stt_url
        self.session = _stt_session

    async def transcribe(self, audio_data: bytes, audio_format: str = "webm") -> dict:
        """Convert audio to text transcript.

        Args:
            audio_data: Raw audio bytes (WebM from browser)
            audio_format: Input format (webm, ogg, etc)

        Returns:
            {"transcript": str, "confidence": float, "error": Optional[str]}
        """
        try:
            # Convert audio to FLAC (16kHz, mono, s16)
            flac_data = await self._convert_to_flac(audio_data, audio_format)

            if not flac_data:
                return {"transcript": "", "confidence": 0.0, "error": "Audio conversion failed"}

            # Call Google Speech API v2
            transcript, confidence = await self._call_google_stt(flac_data)

            return {
                "transcript": transcript,
                "confidence": confidence,
                "error": None
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return {"transcript": "", "confidence": 0.0, "error": str(e)}

    async def _convert_to_flac(self, audio_data: bytes, input_format: str) -> Optional[bytes]:
        """Convert audio to FLAC using ffmpeg subprocess."""
        try:
            # Run ffmpeg in thread pool (blocking I/O)
            loop = asyncio.get_event_loop()
            flac_data = await loop.run_in_executor(
                None,
                self._ffmpeg_convert,
                audio_data,
                input_format
            )
            return flac_data

        except Exception as e:
            logger.error(f"ffmpeg conversion error: {e}")
            return None

    def _ffmpeg_convert(self, audio_data: bytes, input_format: str) -> bytes:
        """Synchronous ffmpeg conversion (called in thread pool)."""
        # ffmpeg: input format -> FLAC (16kHz, mono, s16)
        proc = subprocess.Popen(
            [
                'ffmpeg',
                '-i', 'pipe:0',          # Read from stdin
                '-f', input_format,      # Input format
                '-ar', '16000',          # Sample rate 16kHz
                '-ac', '1',              # Mono
                '-sample_fmt', 's16',    # 16-bit signed
                '-f', 'flac',            # Output format
                'pipe:1'                 # Write to stdout
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = proc.communicate(input=audio_data, timeout=10)

        if proc.returncode != 0:
            stderr_text = stderr.decode('utf-8', errors='replace')
            logger.error(f"ffmpeg failed (rc={proc.returncode}): {stderr_text[:500]}")
            raise RuntimeError(f"ffmpeg failed: {stderr_text[:500]}")

        return stdout

    async def _call_google_stt(self, flac_data: bytes) -> tuple[str, float]:
        """Call Google Speech API v2 with FLAC audio."""
        url = f"{self.api_url}?key={self.api_key}&lang=id-ID"

        # Run requests in thread pool (blocking I/O)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.post(url, data=flac_data, timeout=10)
        )

        if response.status_code != 200:
            raise RuntimeError(f"Google STT API error: {response.status_code}")

        # Parse response (JSON lines format)
        lines = response.text.strip().split('\n')
        for line in lines:
            if not line:
                continue
            try:
                data = json.loads(line)
                if 'result' in data and data['result']:
                    result = data['result'][0]
                    if 'alternative' in result and result['alternative']:
                        alt = result['alternative'][0]
                        transcript = alt.get('transcript', '')
                        confidence = alt.get('confidence', 0.0)
                        return transcript, confidence
            except json.JSONDecodeError:
                continue

        return "", 0.0
