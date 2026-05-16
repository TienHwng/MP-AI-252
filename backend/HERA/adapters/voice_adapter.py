"""Voice adapter for HERA.

The orchestrator already speaks text, so this adapter keeps voice I/O at the
transport edge:

1. Speech-to-text produces a normal text command.
2. The text command is sent through ``Orchestrator.handle()``.
3. The assistant response can optionally be spoken with ``pyttsx3``.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import Any

from agents.orchestrator import Orchestrator
from core.message import AgentResponse, MessageSource, UserMessage


@dataclass(slots=True)
class VoiceTurn:
	"""Result of one voice interaction."""

	transcript: str
	response: AgentResponse


class VoiceAdapter:
	"""Local STT/TTS adapter.

	``SpeechRecognition`` is used for microphone/WAV transcription. ``pyttsx3``
	is optional and only used to speak the assistant response. Both imports are
	lazy so the normal web runtime does not require audio dependencies.
	"""

	def __init__(
		self,
		orchestrator: Orchestrator,
		*,
		language: str = "vi-VN",
		enable_tts: bool = True,
	) -> None:
		self.orch = orchestrator
		self.language = language
		self.enable_tts = enable_tts

	async def handle_text(
		self,
		text: str,
		chat_id: str = "voice",
		metadata: dict[str, Any] | None = None,
	) -> AgentResponse:
		"""Send already-transcribed voice text through the HERA pipeline."""
		transcript = " ".join(str(text or "").split())
		if not transcript:
			raise ValueError("Voice transcript is empty.")
		message = UserMessage(
			text=transcript,
			chat_id=chat_id,
			source=MessageSource.VOICE,
			metadata={
				"session_id": chat_id,
				"input_modality": "voice",
				**(metadata or {}),
			},
		)
		return await self.orch.handle(message)

	async def handle_audio(
		self,
		audio_bytes: bytes,
		chat_id: str = "voice",
		metadata: dict[str, Any] | None = None,
	) -> VoiceTurn:
		"""Transcribe WAV/AIFF/FLAC bytes, orchestrate, and optionally speak."""
		transcript = await asyncio.to_thread(self.transcribe_audio_bytes, audio_bytes)
		response = await self.handle_text(transcript, chat_id=chat_id, metadata=metadata)
		await self.speak(response.text)
		return VoiceTurn(transcript=transcript, response=response)

	async def listen_once(
		self,
		chat_id: str = "voice_local",
		metadata: dict[str, Any] | None = None,
	) -> VoiceTurn:
		"""Capture one microphone phrase, process it, and optionally speak back."""
		transcript = await asyncio.to_thread(self.listen_for_text)
		response = await self.handle_text(transcript, chat_id=chat_id, metadata=metadata)
		await self.speak(response.text)
		return VoiceTurn(transcript=transcript, response=response)

	def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
		"""Transcribe audio bytes supported by ``speech_recognition.AudioFile``."""
		sr = self._speech_recognition()
		recognizer = sr.Recognizer()
		with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
			audio = recognizer.record(source)
		return self._recognize(recognizer, audio)

	def listen_for_text(self) -> str:
		"""Listen to the default microphone and return recognized text."""
		sr = self._speech_recognition()
		recognizer = sr.Recognizer()
		with sr.Microphone() as source:
			recognizer.adjust_for_ambient_noise(source, duration=0.4)
			audio = recognizer.listen(source)
		return self._recognize(recognizer, audio)

	async def speak(self, text: str) -> None:
		"""Speak text with pyttsx3 when enabled and installed."""
		if not self.enable_tts or not text:
			return
		await asyncio.to_thread(self._speak_sync, text)

	def _recognize(self, recognizer: Any, audio: Any) -> str:
		try:
			return recognizer.recognize_google(audio, language=self.language)
		except Exception as exc:
			raise RuntimeError(f"Could not transcribe voice input: {exc}") from exc

	def _speak_sync(self, text: str) -> None:
		try:
			import pyttsx3
		except ImportError as exc:
			raise RuntimeError(
				"pyttsx3 is required for voice playback. Install it with "
				"`pip install pyttsx3`.",
			) from exc
		engine = pyttsx3.init()
		engine.say(text)
		engine.runAndWait()

	@staticmethod
	def _speech_recognition() -> Any:
		try:
			import speech_recognition as sr
		except ImportError as exc:
			raise RuntimeError(
				"SpeechRecognition is required for voice transcription. Install it "
				"with `pip install SpeechRecognition PyAudio`.",
			) from exc
		return sr
