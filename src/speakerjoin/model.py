"""Immutable data types shared by readers, the aligner and the writers."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


@dataclass(frozen=True, slots=True)
class Word:
    """One recognized word. ``start``/``end`` are seconds, or None when the STT gave none."""

    text: str
    start: float | None
    end: float | None
    confidence: float | None = None
    speaker: str | None = None  # speaker label the STT itself attached (informational)


@dataclass(frozen=True, slots=True)
class Segment:
    """A transcript segment (a subtitle cue, a sentence, an utterance)."""

    start: float
    end: float
    text: str
    words: tuple[Word, ...] = ()
    speaker: str | None = None  # speaker label the STT itself attached (informational)


@dataclass(frozen=True, slots=True)
class Transcript:
    segments: tuple[Segment, ...]
    source_format: str

    @property
    def words(self) -> tuple[Word, ...]:
        return tuple(w for seg in self.segments for w in seg.words)


@dataclass(frozen=True, slots=True)
class Turn:
    """One diarization speaker turn. Turns of different speakers may overlap."""

    start: float
    end: float
    speaker: str


@dataclass(frozen=True, slots=True)
class Diarization:
    turns: tuple[Turn, ...]
    source_format: str
    exclusive: bool = False


@dataclass(frozen=True, slots=True)
class AssignedWord:
    """A word with the speaker chosen for it and the quality flags raised for it."""

    word: Word
    speaker: str | None
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Utterance:
    """A run of consecutive words that share one speaker."""

    speaker: str | None
    start: float
    end: float
    words: tuple[AssignedWord, ...]

    @property
    def text(self) -> str:
        return " ".join(w.word.text for w in self.words)


@dataclass(frozen=True, slots=True)
class Report:
    """Numeric alignment quality. See the README for what each metric means."""

    words_total: int
    words_untimed: int
    unassigned: int
    unassigned_ratio: float
    filled_nearest: int
    overlap_words: int
    overlap_ratio: float
    boundary_words: int
    boundary_ratio: float
    segments_multi_speaker: int
    segment_word_disagree: int
    segment_word_disagree_ratio: float
    speaker_changes: int
    dominant_speaker_share: float
    speech_without_words_sec: float
    talk_time: dict[str, float] = field(default_factory=dict)
    word_share: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):
            name = f.name
            value = getattr(self, name)
            if isinstance(value, float):
                value = round(value, 6)
            elif isinstance(value, dict):
                value = {k: round(v, 6) for k, v in value.items()}
            out[name] = value
        return out

    def metrics(self) -> dict[str, float]:
        """Scalar metrics usable in ``--fail-on`` expressions."""
        return {k: v for k, v in self.to_dict().items() if isinstance(v, (int, float))}


@dataclass(frozen=True, slots=True)
class MergeResult:
    words: tuple[AssignedWord, ...]
    utterances: tuple[Utterance, ...]
    report: Report
    options: dict[str, Any] = field(default_factory=dict)
