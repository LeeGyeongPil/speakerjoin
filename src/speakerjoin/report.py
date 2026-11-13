"""Alignment quality metrics and ``--fail-on`` threshold checks."""

from __future__ import annotations

import operator
import re
from bisect import bisect_left
from collections.abc import Sequence

from .errors import ThresholdSyntaxError
from .model import AssignedWord, Report, Turn

_EXPR = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
_OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def _union_length(intervals: list[tuple[float, float]]) -> float:
    total = 0.0
    current_end = None
    current_start = 0.0
    for a, b in sorted(intervals):
        if current_end is None or a > current_end:
            if current_end is not None:
                total += current_end - current_start
            current_start, current_end = a, b
        else:
            current_end = max(current_end, b)
    if current_end is not None:
        total += current_end - current_start
    return total


def _speech_without_words(words: Sequence[AssignedWord], turns: Sequence[Turn]) -> float:
    """Total length of turns that no word overlaps (speech the STT produced no words for)."""
    spans = sorted((w.word.start, w.word.end) for w in words)  # type: ignore[type-var]
    starts = [a for a, _ in spans]
    prefix_end: list[float] = []
    for _, b in spans:
        prefix_end.append(b if not prefix_end else max(prefix_end[-1], b))
    total = 0.0
    for t in turns:
        k = bisect_left(starts, t.end)
        has_word = k > 0 and prefix_end[k - 1] > t.start
        if not has_word:
            total += t.end - t.start
    return total


def build_report(
    words: Sequence[AssignedWord],
    turns: Sequence[Turn],
    segments_multi_speaker: int,
    segment_word_disagree: int,
) -> Report:
    total = len(words)
    unassigned = sum(1 for w in words if w.speaker is None)
    overlap = sum(1 for w in words if "overlap" in w.flags)
    boundary = sum(1 for w in words if "boundary" in w.flags)

    counts: dict[str, int] = {}
    changes = 0
    previous: str | None = None
    for w in words:
        if w.speaker is None:
            continue
        counts[w.speaker] = counts.get(w.speaker, 0) + 1
        if previous is not None and w.speaker != previous:
            changes += 1
        previous = w.speaker
    assigned = sum(counts.values())
    share = {s: c / assigned for s, c in sorted(counts.items())}

    per_speaker: dict[str, list[tuple[float, float]]] = {}
    for t in turns:
        per_speaker.setdefault(t.speaker, []).append((t.start, t.end))
    talk = {s: _union_length(iv) for s, iv in sorted(per_speaker.items())}

    return Report(
        words_total=total,
        words_untimed=sum(1 for w in words if "interpolated" in w.flags),
        unassigned=unassigned,
        unassigned_ratio=_ratio(unassigned, total),
        filled_nearest=sum(1 for w in words if "filled_nearest" in w.flags),
        overlap_words=overlap,
        overlap_ratio=_ratio(overlap, total),
        boundary_words=boundary,
        boundary_ratio=_ratio(boundary, total),
        segments_multi_speaker=segments_multi_speaker,
        segment_word_disagree=segment_word_disagree,
        segment_word_disagree_ratio=_ratio(segment_word_disagree, total),
        speaker_changes=changes,
        dominant_speaker_share=max(share.values(), default=0.0),
        speech_without_words_sec=_speech_without_words(words, turns),
        talk_time=talk,
        word_share=share,
    )


def check_thresholds(report: Report, exprs: Sequence[str]) -> list[str]:
    """Evaluate ``"metric<op>number"`` expressions; return one line per expression that is true.

    An empty list means every threshold passed. Raises :class:`ThresholdSyntaxError` for a
    malformed expression or an unknown metric.
    """
    metrics = report.metrics()
    failed = []
    for expr in exprs:
        match = _EXPR.match(expr)
        if not match:
            raise ThresholdSyntaxError("threshold_syntax", expr=expr)
        name, op, raw = match.groups()
        if name not in metrics:
            raise ThresholdSyntaxError(
                "threshold_metric", name=name, expr=expr, available=", ".join(sorted(metrics))
            )
        value, limit = metrics[name], float(raw)
        if _OPS[op](value, limit):
            failed.append(f"{name}={round(value, 4)} {op} {raw}")
    return failed
