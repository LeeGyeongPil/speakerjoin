"""Public loading functions: pick the right reader and return the shared model."""

from __future__ import annotations

import os
from typing import Any

from .detect import ALL_FORMATS, DIAR_FORMATS, STT_FORMATS, detect_format
from .errors import FormatError, UnknownFormatError
from .model import Diarization, Transcript
from .readers import diar, read_source, stt, subtitles


def load_transcript(
    src: str | os.PathLike[str] | dict[str, Any], *, format: str = "auto"
) -> Transcript:
    """Read a speech-to-text result (file path, text, or parsed JSON dict)."""
    data, label = read_source(src)
    if format != "auto" and format not in STT_FORMATS:
        raise UnknownFormatError(f"format={format!r}", STT_FORMATS)
    name = detect_format(data, label=label) if format == "auto" else format
    if name in DIAR_FORMATS:
        raise FormatError("wrong_role_diar", label=label, name=name)
    if name in ("srt", "vtt"):
        if not isinstance(data, str):
            raise FormatError("must_be_text", label=label, name=name, got=type(data).__name__)
        return subtitles.read_srt(data) if name == "srt" else subtitles.read_vtt(data)
    if not isinstance(data, dict):
        raise FormatError("must_be_object", label=label, name=name)
    return stt.READERS[name](data)


def load_diarization(
    src: str | os.PathLike[str] | dict[str, Any] | list[Any] | object,
    *,
    format: str = "auto",
    file_id: str | None = None,
    prefer_exclusive: bool = True,
) -> Diarization:
    """Read speaker turns from a file, parsed JSON, ``(start, end, speaker)`` tuples,
    or a pyannote ``Annotation`` (duck-typed, pyannote is never imported)."""
    if format != "auto" and format not in DIAR_FORMATS:
        raise UnknownFormatError(f"format={format!r}", DIAR_FORMATS)
    if hasattr(src, "itertracks"):
        return diar.read_annotation(src)
    if isinstance(src, (list, tuple)) and src and all(isinstance(i, (tuple, list)) for i in src):
        return diar.read_tuples(src)
    data, label = read_source(src)
    name = detect_format(data, label=label) if format == "auto" else format
    if name in STT_FORMATS:
        raise FormatError("wrong_role_stt", label=label, name=name)
    if name == "rttm":
        if not isinstance(data, str):
            raise FormatError("must_be_text", label=label, name=name, got=type(data).__name__)
        return diar.read_rttm(data, label, file_id)
    if name == "pyannoteai":
        if not isinstance(data, dict):
            raise FormatError("must_be_object", label=label, name=name)
        return diar.read_pyannoteai(data, prefer_exclusive)
    if name == "json":
        return diar.read_json_turns(data)
    raise UnknownFormatError(label, ALL_FORMATS)
