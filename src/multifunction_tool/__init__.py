"""Multifunction tool: Whisper transcription, audio extraction, token counting."""

from multifunction_tool.core import count_tokens, extract_audio, transcribe_audio

__all__ = ["transcribe_audio", "extract_audio", "count_tokens"]
__version__ = "1.1.0"
