"""Format detection from the shape of the data (no file extensions needed)."""

from __future__ import annotations

from typing import Any

from .errors import UnknownFormatError

STT_FORMATS = (
    "openai_verbose",
    "openai_diarized",
    "faster_whisper",
    "whisperx",
    "deepgram",
    "assemblyai",
    "srt",
    "vtt",
)
DIAR_FORMATS = ("rttm", "pyannoteai", "json")
ALL_FORMATS = STT_FORMATS + DIAR_FORMATS


def detect_format(data: Any, *, label: str = "the input") -> str:
    """Return the format name for parsed JSON (dict/list) or raw text.

    Raises :class:`UnknownFormatError` (listing the supported formats) when nothing matches.
    """
    if isinstance(data, str):
        found = _detect_text(data)
    elif isinstance(data, dict):
        found = _detect_dict(data)
    elif isinstance(data, list):
        found = _detect_list(data)
    else:
        found = None
    if found is None:
        raise UnknownFormatError(label, ALL_FORMATS)
    return found


def _detect_text(text: str) -> str | None:
    stripped = text.lstrip("﻿ \t\r\n")
    if stripped.startswith("WEBVTT"):
        return "vtt"
    for line in stripped.splitlines():
        line = line.strip()
        if not line or line.startswith(";;"):
            continue
        if line.split()[0] == "SPEAKER":
            return "rttm"
        break
    if "-->" in stripped:
        return "srt"
    return None


def _first_word(segments: list[Any]) -> dict[str, Any] | None:
    for seg in segments:
        if isinstance(seg, dict):
            for word in seg.get("words") or []:
                if isinstance(word, dict):
                    return word
    return None


def _detect_dict(d: dict[str, Any]) -> str | None:
    results = d.get("results")
    if isinstance(results, dict) and "channels" in results:
        return "deepgram"
    output = d.get("output")
    if isinstance(output, dict) and ("diarization" in output or "exclusiveDiarization" in output):
        return "pyannoteai"
    if "diarization" in d or "exclusiveDiarization" in d:
        return "pyannoteai"
    if "turns" in d and "segments" not in d:
        return "json"
    if "word_segments" in d:
        return "whisperx"
    words = d.get("words")
    utterances = d.get("utterances")
    if isinstance(words, list) and words and isinstance(words[0], dict):
        if "text" in words[0] and "word" not in words[0]:
            return "assemblyai"
        if "word" in words[0]:
            return "openai_verbose"
    if isinstance(utterances, list):
        return "assemblyai"
    segments = d.get("segments")
    if isinstance(segments, list):
        first = segments[0] if segments else None
        probe = _first_word(segments)
        if probe is not None:
            if "probability" in probe:
                return "faster_whisper"
            if "score" in probe or (isinstance(first, dict) and "speaker" in first):
                return "whisperx"
            return "faster_whisper"
        if isinstance(first, dict) and "speaker" in first:
            return "openai_diarized"
        return "openai_verbose"
    return None


def _detect_list(items: list[Any]) -> str | None:
    if all(isinstance(i, dict) and {"start", "end", "speaker"} <= i.keys() for i in items):
        return "json"
    return None
