"""Aligning words (or segments) with speaker turns.

Algorithm in short: every word gets an effective time span; spans are swept in start order
against turns sorted by start (an "active" list plus a bisect window), so the cost is about
O((W + T) log T) instead of W x T. The chosen speaker is the one with the largest summed
overlap ("overlap") or the one whose turn contains the word midpoint ("midpoint").
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import replace
from typing import NamedTuple

from .errors import ConfigError
from .model import (
    AssignedWord,
    Diarization,
    MergeResult,
    Segment,
    Transcript,
    Turn,
    Word,
)
from .report import build_report
from .utterances import build_utterances

STRATEGIES = ("overlap", "midpoint")
UNITS = ("auto", "word", "segment")
_EPS = 1e-9


class Result(NamedTuple):
    speaker: str | None
    overlap: bool
    boundary: bool
    filled: bool


class TurnIndex:
    """Turns sorted for fast interval queries."""

    def __init__(self, turns: tuple[Turn, ...]) -> None:
        ordered = sorted(turns, key=lambda t: (t.start, t.end, t.speaker))
        self.starts = [t.start for t in ordered]
        self.ends = [t.end for t in ordered]
        self.speakers = [t.speaker for t in ordered]
        self.edges = sorted({*self.starts, *self.ends})
        self.ends_sorted = sorted(self.ends)
        self._by_end = sorted(range(len(ordered)), key=lambda k: (self.ends[k], k))

    def near_edge(self, x: float, tolerance: float) -> bool:
        i = bisect_left(self.edges, x - tolerance - _EPS)
        return i < len(self.edges) and self.edges[i] <= x + tolerance + _EPS

    def assign_many(
        self,
        spans: list[tuple[float, float]],
        strategy: str,
        fill_nearest: bool,
        tolerance: float,
    ) -> list[Result]:
        """Assign every ``(a, b)`` span (with ``b > a``). Order of the result matches ``spans``."""
        starts, ends, speakers = self.starts, self.ends, self.speakers
        n = len(starts)
        results: list[Result | None] = [None] * len(spans)
        order = sorted(range(len(spans)), key=lambda i: spans[i][0])
        active: list[int] = []
        p = 0
        for i in order:
            a, b = spans[i]
            while p < n and starts[p] <= a:
                active.append(p)
                p += 1
            active = [k for k in active if ends[k] > a]
            hi = bisect_left(starts, b, lo=p)
            candidates = active + list(range(p, hi))  # ascending turn order

            sums: dict[str, float] = {}
            for k in candidates:
                ov = min(ends[k], b) - max(starts[k], a)
                if ov > 0:
                    sums[speakers[k]] = sums.get(speakers[k], 0.0) + ov
            mid = (a + b) / 2
            containing: list[str] = []
            for k in candidates:
                if starts[k] <= mid < ends[k] and speakers[k] not in containing:
                    containing.append(speakers[k])

            if strategy == "overlap":
                speaker = _argmax(sums)
            elif len(containing) == 1:
                speaker = containing[0]
            elif containing:
                speaker = _argmax({s: sums.get(s, 0.0) for s in containing})
            else:
                speaker = None

            filled = False
            if speaker is None and fill_nearest:
                speaker = _argmax(sums) if sums else self._nearest(a, b)
                filled = speaker is not None
            results[i] = Result(
                speaker,
                len(containing) >= 2,
                self.near_edge(a, tolerance) or self.near_edge(b, tolerance),
                filled,
            )
        return results  # type: ignore[return-value]

    def _nearest(self, a: float, b: float) -> str | None:
        """Speaker of the closest turn when nothing overlaps [a, b]."""
        best: tuple[float, str] | None = None
        j = bisect_right(self.ends_sorted, a) - 1
        if j >= 0:
            k = self._by_end[j]
            best = (a - self.ends[k], self.speakers[k])
        k2 = bisect_left(self.starts, b)
        if k2 < len(self.starts):
            gap = self.starts[k2] - b
            if best is None or gap < best[0]:  # a tie prefers the earlier speaker
                best = (gap, self.speakers[k2])
        return None if best is None else best[1]


def _argmax(sums: dict[str, float]) -> str | None:
    best: str | None = None
    best_value = 0.0
    for speaker, value in sums.items():
        if value > best_value:
            best, best_value = speaker, value
    return best


def _widen(a: float, b: float, min_dur: float) -> tuple[float, float]:
    """Give a (near) zero-length span a minimum width centred on it."""
    if b - a >= min_dur:
        return a, b
    mid = a if b <= a else (a + b) / 2
    return mid - min_dur / 2, mid + min_dur / 2


def _resolve_times(seg: Segment, min_dur: float) -> list[tuple[Word, set[str]]]:
    """Effective times for the words of one segment, plus timing flags."""
    words = seg.words
    spans: list[tuple[float, float] | None] = []
    flags: list[set[str]] = []
    for w in words:
        f: set[str] = set()
        if w.start is None:
            spans.append(None)
        else:
            end = w.start if w.end is None else w.end
            if end <= w.start:
                f.add("zero_length")
            spans.append(_widen(w.start, end, min_dur))
        flags.append(f)
    i = 0
    while i < len(words):
        if spans[i] is not None:
            i += 1
            continue
        j = i
        while j < len(words) and spans[j] is None:
            j += 1
        prev = spans[i - 1] if i > 0 else None
        nxt = spans[j] if j < len(words) else None
        lower = prev[1] if prev else seg.start
        upper = nxt[0] if nxt else seg.end
        upper = max(upper, lower)
        count = j - i
        for k in range(count):
            a = lower + (upper - lower) * k / count
            b = lower + (upper - lower) * (k + 1) / count
            spans[i + k] = _widen(a, b, min_dur)
            flags[i + k].add("interpolated")
        i = j
    out = []
    for w, span, f in zip(words, spans, flags, strict=True):
        assert span is not None
        out.append((replace(w, start=span[0], end=span[1]), f))
    return out


class _Item(NamedTuple):
    word: Word
    flags: set[str]
    seg_index: int
    span_index: int  # index into the batch of spans (word span or its segment span)


def merge(
    transcript: Transcript,
    diarization: Diarization,
    *,
    strategy: str = "overlap",
    unit: str = "auto",
    fill_nearest: bool = False,
    tolerance: float = 0.2,
    min_word_dur: float = 0.02,
) -> MergeResult:
    """Assign a speaker to every word of ``transcript`` using ``diarization``.

    ``unit="auto"`` works per word when a segment has timed words and falls back to the whole
    segment otherwise (subtitles, OpenAI diarized JSON). ``unit="segment"`` forces segment
    level for everything, which is what segment-based tools do.
    """
    if strategy not in STRATEGIES:
        raise ConfigError("opt_strategy", allowed=str(STRATEGIES), got=strategy)
    if unit not in UNITS:
        raise ConfigError("opt_unit", allowed=str(UNITS), got=unit)
    if min_word_dur <= 0:
        raise ConfigError("opt_min_word_dur")
    if tolerance < 0:
        raise ConfigError("opt_tolerance")

    spans: list[tuple[float, float]] = []
    items: list[_Item] = []
    word_level_segments: list[tuple[int, list[int]]] = []  # (seg span index, item indexes)

    for si, seg in enumerate(transcript.segments):
        if unit == "segment":
            word_level = False
        elif unit == "word":
            word_level = bool(seg.words)
        else:
            word_level = any(w.start is not None for w in seg.words)
        seg_span = _widen(seg.start, seg.end, min_word_dur)
        spans.append(seg_span)
        seg_index = len(spans) - 1
        if word_level:
            members = []
            for w, f in _resolve_times(seg, min_word_dur):
                spans.append((w.start, w.end))  # type: ignore[arg-type]
                items.append(_Item(w, f, si, len(spans) - 1))
                members.append(len(items) - 1)
            word_level_segments.append((seg_index, members))
        elif seg.words:
            for w, f in _resolve_times(seg, min_word_dur):
                items.append(_Item(w, f, si, seg_index))
        else:
            f = {"zero_length"} if seg.end <= seg.start else set()
            items.append(_Item(Word(seg.text, seg.start, seg.end), f, si, seg_index))

    results = TurnIndex(diarization.turns).assign_many(spans, strategy, fill_nearest, tolerance)

    assigned: list[AssignedWord] = []
    for item in items:
        res = results[item.span_index]
        flags = set(item.flags)
        if res.speaker is None:
            flags.add("unassigned")
        if res.filled:
            flags.add("filled_nearest")
        if res.overlap:
            flags.add("overlap")
        if res.boundary:
            flags.add("boundary")
        assigned.append(AssignedWord(item.word, res.speaker, frozenset(flags)))

    multi = 0
    disagree = 0
    for seg_index, members in word_level_segments:
        seg_speaker = results[seg_index].speaker
        speakers = {assigned[m].speaker for m in members} - {None}
        multi += len(speakers) >= 2
        disagree += sum(1 for m in members if assigned[m].speaker != seg_speaker)

    if not word_level_segments:
        effective_unit = "segment"
    elif len(word_level_segments) == len(transcript.segments):
        effective_unit = "word"
    else:
        effective_unit = "mixed"
    options = {
        "strategy": strategy,
        "unit": unit,
        "effective_unit": effective_unit,
        "fill_nearest": fill_nearest,
        "tolerance": tolerance,
        "min_word_dur": min_word_dur,
        "stt_format": transcript.source_format,
        "diarization_format": diarization.source_format,
        "diarization_exclusive": diarization.exclusive,
    }
    utterances = build_utterances(assigned)
    report = build_report(assigned, diarization.turns, multi, disagree)
    return MergeResult(tuple(assigned), utterances, report, options)
