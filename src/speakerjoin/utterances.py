"""Grouping words into utterances and subtitle cues."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .model import AssignedWord, Utterance

UNASSIGNED_LABEL = "UNKNOWN"


def build_utterances(words: Iterable[AssignedWord]) -> tuple[Utterance, ...]:
    """Merge consecutive words of one speaker; a speaker change always starts a new utterance."""
    out: list[Utterance] = []
    group: list[AssignedWord] = []

    def flush() -> None:
        if group:
            start = group[0].word.start
            end = max(w.word.end for w in group)  # type: ignore[type-var]
            out.append(Utterance(group[0].speaker, start, end, tuple(group)))  # type: ignore[arg-type]

    for w in words:
        if group and w.speaker != group[0].speaker:
            flush()
            group = []
        group.append(w)
    flush()
    return tuple(out)


def split_cues(
    utterance: Utterance, max_chars: int = 42, max_duration: float = 7.0
) -> list[tuple[AssignedWord, ...]]:
    """Cut an utterance into cues no longer than ``max_chars`` characters or ``max_duration``
    seconds (a single oversize word or segment still becomes its own cue)."""
    cues: list[list[AssignedWord]] = []
    current: list[AssignedWord] = []
    chars = 0
    for w in utterance.words:
        add = len(w.word.text) + (1 if current else 0)
        too_long = chars + add > max_chars
        too_slow = bool(current) and (w.word.end - current[0].word.start) > max_duration  # type: ignore[operator]
        if current and (too_long or too_slow):
            cues.append(current)
            current, chars, add = [], 0, len(w.word.text)
        current.append(w)
        chars += add
    if current:
        cues.append(current)
    return [tuple(c) for c in cues]


def label(speaker: str | None, speaker_map: Mapping[str, str] | None) -> str:
    """Display name for a speaker (``speaker_map`` renames, None becomes UNKNOWN)."""
    if speaker is None:
        return UNASSIGNED_LABEL
    return (speaker_map or {}).get(speaker, speaker)
