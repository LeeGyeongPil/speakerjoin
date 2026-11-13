"""SRT and WebVTT readers (cue level; subtitles carry no word timing)."""

from __future__ import annotations

import html
import re

from ..errors import FormatError
from ..model import Segment, Transcript

_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
_TIMING = re.compile(rf"^\s*{_TIME}\s*-->\s*{_TIME}")
_VOICE = re.compile(r"<v(?:\.[^\s>]+)*\s+([^>]+)>")
_TAG = re.compile(r"<[^>]*>")


def _seconds(h: str | None, m: str, s: str, frac: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")) / 1000.0


def _parse(text: str, fmt: str) -> Transcript:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip("﻿\n"))
    segments = []
    for number, block in enumerate(blocks, 1):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        if fmt == "vtt" and (lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION"))):
            continue
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            raise FormatError("sub_no_timing", fmt=fmt.upper(), number=number, line=lines[0])
        match = _TIMING.match(lines[idx])
        if not match:
            raise FormatError("sub_bad_timing", fmt=fmt.upper(), number=number, line=lines[idx])
        g = match.groups()
        start, end = _seconds(*g[:4]), _seconds(*g[4:])
        raw = " ".join(lines[idx + 1 :])
        voice = _VOICE.search(raw)
        speaker = voice.group(1).strip() if voice else None
        clean = " ".join(html.unescape(_TAG.sub("", raw)).split())
        if clean:
            segments.append(Segment(start, end, clean, (), speaker))
    return Transcript(tuple(segments), fmt)


def read_srt(text: str) -> Transcript:
    return _parse(text, "srt")


def read_vtt(text: str) -> Transcript:
    return _parse(text, "vtt")
