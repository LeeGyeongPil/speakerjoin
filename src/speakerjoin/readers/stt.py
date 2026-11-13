"""Speech-to-text JSON readers. All of them return times in seconds."""

from __future__ import annotations

from bisect import bisect_right
from typing import Any

from ..errors import FormatError
from ..model import Segment, Transcript, Word
from . import num

_SENTENCE_END = (".", "?", "!", "。", "？", "！")


def _word(text: Any, start: Any, end: Any, where: str, conf: Any = None, speaker: Any = None):
    """Build a Word; returns None for blank text. Text is stripped (faster-whisper adds a space)."""
    clean = str(text if text is not None else "").strip()
    if not clean:
        return None
    return Word(
        text=clean,
        start=num(start, f"{where}.start"),
        end=num(end, f"{where}.end"),
        confidence=num(conf, f"{where}.confidence"),
        speaker=None if speaker is None else str(speaker),
    )


def _need_list(value: Any, where: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise FormatError("expected_list", where=where, got=type(value).__name__)
    return value


def _need_dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormatError("expected_object", where=where, got=type(value).__name__)
    return value


def _segment(text: str, words: list[Word], start: float | None, end: float | None, speaker=None):
    """Segment with bounds taken from the source or, failing that, from the timed words."""
    timed = [w for w in words if w.start is not None]
    if start is None:
        start = min((w.start for w in timed), default=None)
    if end is None:
        end = max((w.end if w.end is not None else w.start for w in timed), default=None)
    if start is None or end is None:
        raise FormatError("segment_no_bounds")
    text = " ".join(text.split()) or " ".join(w.text for w in words)
    return Segment(start=start, end=end, text=text, words=tuple(words), speaker=speaker)


def _group_words(words: list[Word], max_gap: float = 1.0, max_words: int = 40) -> list[Segment]:
    """Split a flat word list into sentence-like segments (for formats without segments)."""
    segments: list[Segment] = []
    current: list[Word] = []
    for i, w in enumerate(words):
        current.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (
            nxt.start - w.end
            if nxt is not None and nxt.start is not None and w.end is not None
            else 0.0
        )
        if (
            nxt is None
            or w.text.endswith(_SENTENCE_END)
            or gap > max_gap
            or len(current) >= max_words
        ):
            segments.append(_segment("", current, None, None))
            current = []
    return segments


def _segments_json(data: dict[str, Any], what: str) -> Transcript:
    """Shared by faster-whisper and WhisperX: ``segments[].words[]``."""
    out = []
    for i, seg in enumerate(_need_list(data.get("segments"), "segments")):
        seg = _need_dict(seg, f"segments[{i}]")
        words = []
        for j, raw in enumerate(_need_list(seg.get("words"), f"segments[{i}].words")):
            raw = _need_dict(raw, f"segments[{i}].words[{j}]")
            conf = raw.get("probability", raw.get("score"))
            w = _word(
                raw.get("word", raw.get("text")), raw.get("start"), raw.get("end"),
                f"segments[{i}].words[{j}]", conf, raw.get("speaker"),
            )  # fmt: skip
            if w is not None:
                words.append(w)
        out.append(
            _segment(
                str(seg.get("text", "")),
                words,
                num(seg.get("start"), f"segments[{i}].start"),
                num(seg.get("end"), f"segments[{i}].end"),
                None if seg.get("speaker") is None else str(seg["speaker"]),
            )  # fmt: skip
        )
    return Transcript(tuple(out), what)


def read_faster_whisper(data: dict[str, Any]) -> Transcript:
    return _segments_json(data, "faster_whisper")


def read_whisperx(data: dict[str, Any]) -> Transcript:
    # Words without ``start`` (numbers, unaligned tokens) are kept with start=None.
    return _segments_json(data, "whisperx")


def read_openai_verbose(data: dict[str, Any]) -> Transcript:
    """OpenAI ``verbose_json``: words live in a top-level list, not inside segments."""
    raw_segments = [
        _need_dict(s, f"segments[{i}]")
        for i, s in enumerate(_need_list(data.get("segments"), "segments"))
    ]
    top_words = []
    for j, raw in enumerate(_need_list(data.get("words"), "words")):
        raw = _need_dict(raw, f"words[{j}]")
        w = _word(raw.get("word"), raw.get("start"), raw.get("end"), f"words[{j}]")
        if w is not None:
            top_words.append(w)
    if not raw_segments:
        return Transcript(tuple(_group_words(top_words)), "openai_verbose")
    bounds = []
    for i, s in enumerate(raw_segments):
        a, b = num(s.get("start"), f"segments[{i}].start"), num(s.get("end"), f"segments[{i}].end")
        if a is None or b is None:
            raise FormatError("segment_needs_numbers", index=i)
        bounds.append((a, b))
    buckets: list[list[Word]] = [[] for _ in raw_segments]
    if top_words:
        starts = [a for a, _ in bounds]
        last = 0
        for w in top_words:
            if w.start is None:
                idx = last  # untimed word: stay with the previous word's segment
            else:
                mid = (w.start + (w.end if w.end is not None else w.start)) / 2
                idx = max(bisect_right(starts, mid) - 1, 0)
                if idx + 1 < len(bounds) and mid > bounds[idx][1]:
                    # in a gap between segments: take the nearer one
                    if bounds[idx + 1][0] - mid < mid - bounds[idx][1]:
                        idx += 1
            buckets[idx].append(w)
            last = idx
    else:  # some servers put words inside segments instead
        for i, s in enumerate(raw_segments):
            for j, raw in enumerate(_need_list(s.get("words"), f"segments[{i}].words")):
                raw = _need_dict(raw, f"segments[{i}].words[{j}]")
                w = _word(
                    raw.get("word"), raw.get("start"), raw.get("end"), f"segments[{i}].words[{j}]"
                )
                if w is not None:
                    buckets[i].append(w)
    segments = [
        _segment(str(s.get("text", "")), buckets[i], bounds[i][0], bounds[i][1])
        for i, s in enumerate(raw_segments)
    ]
    return Transcript(tuple(segments), "openai_verbose")


def read_openai_diarized(data: dict[str, Any]) -> Transcript:
    """OpenAI ``diarized_json``: segments carry a speaker but no word timing."""
    out = []
    for i, seg in enumerate(_need_list(data.get("segments"), "segments")):
        seg = _need_dict(seg, f"segments[{i}]")
        a, b = (
            num(seg.get("start"), f"segments[{i}].start"),
            num(seg.get("end"), f"segments[{i}].end"),
        )
        if a is None or b is None:
            raise FormatError("segment_needs_numbers", index=i)
        speaker = seg.get("speaker")
        out.append(
            Segment(a, b, " ".join(str(seg.get("text", "")).split()), (),
                    None if speaker is None else str(speaker))
        )  # fmt: skip
    return Transcript(tuple(out), "openai_diarized")


def read_deepgram(data: dict[str, Any]) -> Transcript:
    try:
        alt = data["results"]["channels"][0]["alternatives"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise FormatError("deepgram_shape") from exc
    words = []
    for j, raw in enumerate(_need_list(alt.get("words"), "alternatives[0].words")):
        raw = _need_dict(raw, f"words[{j}]")
        text = raw.get("punctuated_word") or raw.get("word")
        w = _word(text, raw.get("start"), raw.get("end"), f"words[{j}]",
                  raw.get("confidence"), raw.get("speaker"))  # fmt: skip
        if w is not None:
            words.append(w)
    return Transcript(tuple(_group_words(words)), "deepgram")


def _ms(value: Any, where: str) -> float | None:
    n = num(value, where)
    return None if n is None else n / 1000.0


def _assembly_words(items: Any, where: str) -> list[Word]:
    words = []
    for j, raw in enumerate(_need_list(items, where)):
        raw = _need_dict(raw, f"{where}[{j}]")
        text = raw.get("text", raw.get("word"))
        w = _word(text, None, None, f"{where}[{j}]", raw.get("confidence"), raw.get("speaker"))
        if w is not None:
            w = Word(
                w.text, _ms(raw.get("start"), f"{where}[{j}].start"),
                _ms(raw.get("end"), f"{where}[{j}].end"), w.confidence, w.speaker,
            )  # fmt: skip
            words.append(w)
    return words


def read_assemblyai(data: dict[str, Any]) -> Transcript:
    """AssemblyAI reports milliseconds; everything is converted to seconds here."""
    utterances = data.get("utterances")
    if isinstance(utterances, list) and utterances:
        segments = []
        for i, utt in enumerate(utterances):
            utt = _need_dict(utt, f"utterances[{i}]")
            words = _assembly_words(utt.get("words"), f"utterances[{i}].words")
            segments.append(
                _segment(
                    str(utt.get("text", "")),
                    words,
                    _ms(utt.get("start"), f"utterances[{i}].start"),
                    _ms(utt.get("end"), f"utterances[{i}].end"),
                    None if utt.get("speaker") is None else str(utt["speaker"]),
                )  # fmt: skip
            )
        return Transcript(tuple(segments), "assemblyai")
    return Transcript(
        tuple(_group_words(_assembly_words(data.get("words"), "words"))), "assemblyai"
    )


READERS = {
    "openai_verbose": read_openai_verbose,
    "openai_diarized": read_openai_diarized,
    "faster_whisper": read_faster_whisper,
    "whisperx": read_whisperx,
    "deepgram": read_deepgram,
    "assemblyai": read_assemblyai,
}
