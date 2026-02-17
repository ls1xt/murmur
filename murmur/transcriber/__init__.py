"""Transcriber factory."""

from __future__ import annotations

from murmur.config import TranscriberConfig
from murmur.transcriber.base import Transcriber


def create_transcriber(config: TranscriberConfig) -> Transcriber:
    """Create a transcriber backend based on config."""
    match config.backend:
        case "assemblyai":
            from murmur.transcriber.assemblyai import AssemblyAITranscriber

            return AssemblyAITranscriber(config)
        case _:
            raise ValueError(f"Unknown transcriber backend: {config.backend!r}")
