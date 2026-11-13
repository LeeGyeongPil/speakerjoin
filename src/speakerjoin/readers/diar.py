"""Diarization readers: RTTM, pyannoteAI job JSON, plain JSON, Python objects."""

from __future__ import annotations

from typing import Any

from ..errors import FormatError
from ..model import Diarization, Turn
from . import num


def _finish(turns: list[Turn], fmt: str, exclusive: bool = False) -> Diarization:
    turns.sort(key=lambda t: (t.start, t.end, t.speaker))
    return Diarization(tuple(turns), fmt, exclusive)


def _turn(start: Any, end: Any, speaker: Any, where: str) -> Turn:
    a, b = num(start, f"{where}.start"), num(end, f"{where}.end")
    if a is None or b is None:
        raise FormatError("start_end_required", where=where)
    if b < a:
        raise FormatError("end_before_start", where=where, end=b, start=a)
    if speaker is None or str(speaker) == "":
        raise FormatError("speaker_missing", where=where)
    return Turn(a, b, str(speaker))


def read_rttm(text: str, label: str, file_id: str | None = None) -> Diarization:
    """RTTM columns 4 and 5 are start and DURATION (not end)."""
    rows: list[tuple[str, Turn]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(";;"):
            continue
        parts = line.split()
        if parts[0] != "SPEAKER":
            continue  # other RTTM record types (SPKR-INFO, ...) are not turns
        where = f"{label}:{lineno}"
        if len(parts) < 8:
            raise FormatError("rttm_fields", where=where, count=len(parts))
        try:
            start, dur = float(parts[3]), float(parts[4])
        except ValueError as exc:
            raise FormatError("rttm_numbers", where=where, start=parts[3], dur=parts[4]) from exc
        if dur < 0:
            raise FormatError("rttm_negative_duration", where=where, dur=dur)
        rows.append((parts[1], Turn(start, start + dur, parts[7])))
    ids = sorted({fid for fid, _ in rows})
    if file_id is None:
        if len(ids) > 1:
            raise FormatError("rttm_several_ids", label=label, ids=", ".join(ids))
        chosen = rows
    else:
        chosen = [r for r in rows if r[0] == file_id]
        if not chosen:
            raise FormatError(
                "rttm_no_file_id", label=label, file_id=file_id, available=", ".join(ids) or "-"
            )
    return _finish([t for _, t in chosen], "rttm")


def read_pyannoteai(data: dict[str, Any], prefer_exclusive: bool = True) -> Diarization:
    output = data.get("output") if isinstance(data.get("output"), dict) else data
    exclusive_items = output.get("exclusiveDiarization")
    plain_items = output.get("diarization")
    use_exclusive = prefer_exclusive and isinstance(exclusive_items, list) and bool(exclusive_items)
    items = exclusive_items if use_exclusive else plain_items
    if not isinstance(items, list):
        raise FormatError("pyannoteai_no_list")
    key = "exclusiveDiarization" if use_exclusive else "diarization"
    turns = [
        _turn(i.get("start"), i.get("end"), i.get("speaker"), f"{key}[{n}]")
        for n, i in enumerate(items)
        if isinstance(i, dict)
    ]
    return _finish(turns, "pyannoteai", exclusive=use_exclusive)


def read_json_turns(data: Any) -> Diarization:
    items = data.get("turns") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise FormatError("json_shape", shape="{start, end, speaker}")
    turns = []
    for n, item in enumerate(items):
        if not isinstance(item, dict):
            raise FormatError("turn_object", where=f"turns[{n}]")
        turns.append(_turn(item.get("start"), item.get("end"), item.get("speaker"), f"turns[{n}]"))
    return _finish(turns, "json")


def read_tuples(items: Any) -> Diarization:
    turns = []
    for n, item in enumerate(items):
        try:
            start, end, speaker = item
        except (TypeError, ValueError) as exc:
            raise FormatError("turn_tuple", where=f"turns[{n}]") from exc
        turns.append(_turn(start, end, speaker, f"turns[{n}]"))
    return _finish(turns, "tuples")


def read_annotation(obj: Any) -> Diarization:
    """Duck-typed pyannote ``Annotation``: needs ``itertracks(yield_label=True)``."""
    turns = []
    for n, (segment, _track, label) in enumerate(obj.itertracks(yield_label=True)):
        turns.append(_turn(segment.start, segment.end, label, f"annotation[{n}]"))
    return _finish(turns, "annotation")
