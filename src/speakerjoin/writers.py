"""Text writers: SRT, WebVTT, JSON, Markdown, plain text."""

from __future__ import annotations

import json
from collections.abc import Mapping

from .model import MergeResult
from .utterances import label, split_cues

SCHEMA_VERSION = 1


def _stamp(seconds: float, sep: str) -> str:
    ms = round(max(seconds, 0.0) * 1000)
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _cues(result: MergeResult, speaker_map, max_chars: int, max_duration: float):
    for utt in result.utterances:
        name = label(utt.speaker, speaker_map)
        for cue in split_cues(utt, max_chars, max_duration):
            text = " ".join(w.word.text for w in cue)
            yield name, cue[0].word.start, max(w.word.end for w in cue), text  # type: ignore[type-var]


def to_srt(
    result: MergeResult,
    *,
    speaker_map: Mapping[str, str] | None = None,
    max_chars: int = 42,
    max_duration: float = 7.0,
) -> str:
    """SRT with a ``[Speaker]`` prefix; a new cue starts at every speaker change."""
    blocks = []
    for n, (name, a, b, text) in enumerate(_cues(result, speaker_map, max_chars, max_duration), 1):
        blocks.append(f"{n}\n{_stamp(a, ',')} --> {_stamp(b, ',')}\n[{name}] {text}\n")
    return "\n".join(blocks)


def _vtt_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_vtt(
    result: MergeResult,
    *,
    speaker_map: Mapping[str, str] | None = None,
    max_chars: int = 42,
    max_duration: float = 7.0,
) -> str:
    """WebVTT with ``<v Speaker>`` voice tags."""
    blocks = ["WEBVTT\n"]
    for name, a, b, text in _cues(result, speaker_map, max_chars, max_duration):
        blocks.append(
            f"{_stamp(a, '.')} --> {_stamp(b, '.')}\n<v {_vtt_escape(name)}>{_vtt_escape(text)}\n"
        )
    return "\n".join(blocks)


def to_json(
    result: MergeResult,
    *,
    speaker_map: Mapping[str, str] | None = None,
    max_chars: int = 42,
    max_duration: float = 7.0,
) -> str:
    """Words (with flags), utterances, the quality report and the options used."""

    def name(speaker: str | None) -> str | None:
        return None if speaker is None else label(speaker, speaker_map)

    doc = {
        "schema": SCHEMA_VERSION,
        "options": result.options,
        "report": result.report.to_dict(),
        "utterances": [
            {
                "speaker": name(u.speaker),
                "start": round(u.start, 3),
                "end": round(u.end, 3),
                "text": u.text,
            }
            for u in result.utterances
        ],
        "words": [
            {
                "text": w.word.text,
                "start": round(w.word.start, 3),  # type: ignore[arg-type]
                "end": round(w.word.end, 3),  # type: ignore[arg-type]
                "speaker": name(w.speaker),
                "flags": sorted(w.flags),
            }
            for w in result.words
        ],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _clock(seconds: float) -> str:
    total = int(max(seconds, 0.0))
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def to_markdown(
    result: MergeResult,
    *,
    speaker_map: Mapping[str, str] | None = None,
    max_chars: int = 42,
    max_duration: float = 7.0,
    title: str = "Transcript",
) -> str:
    """A readable transcript: one paragraph per utterance with speaker and start time."""
    parts = [f"# {title}\n"]
    for utt in result.utterances:
        parts.append(f"**{label(utt.speaker, speaker_map)}** [{_clock(utt.start)}]\n\n{utt.text}\n")
    return "\n".join(parts)


def to_text(
    result: MergeResult,
    *,
    speaker_map: Mapping[str, str] | None = None,
    max_chars: int = 42,
    max_duration: float = 7.0,
) -> str:
    """One ``Speaker: text`` line per utterance."""
    return "".join(f"{label(u.speaker, speaker_map)}: {u.text}\n" for u in result.utterances)
