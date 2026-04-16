"""
Voice Adapter (Stub)
====================
Placeholder for future STT/TTS integration.

The voice pipeline will:
  1. Capture audio → run STT (e.g. Whisper) → produce text
  2. Feed text into ``Orchestrator.handle()`` as a ``UserMessage``
  3. Take ``AgentResponse.text`` → run TTS (e.g. edge-tts / Piper) → play audio

Because the Orchestrator works purely with text, no agent changes are needed.
"""

from __future__ import annotations

from core.message import MessageSource, UserMessage
from agents.orchestrator import Orchestrator


class VoiceAdapter:
    """
    Stub — will be implemented when STT/TTS engines are integrated.

    Example future flow::

        audio_bytes = mic.record(duration=5)
        text = stt_engine.transcribe(audio_bytes)
        msg = UserMessage(text=text, chat_id="voice_local", source=MessageSource.VOICE)
        response = await orchestrator.handle(msg)
        tts_engine.speak(response.text)
    """

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orch = orchestrator

    async def handle_audio(self, audio_bytes: bytes, chat_id: str = "voice") -> str:
        """Transcribe → orchestrate → return text for TTS."""
        raise NotImplementedError(
            "Voice adapter not yet implemented. "
            "Integrate Whisper (STT) and edge-tts/Piper (TTS) here."
        )
