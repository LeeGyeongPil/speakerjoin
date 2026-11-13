"""speakerjoin: join speech-to-text output with speaker diarization.

Typical use::

    from pathlib import Path

    import speakerjoin as sj

    transcript = sj.load_transcript("stt.json")
    diarization = sj.load_diarization("diar.rttm")
    result = sj.merge(transcript, diarization)
    print(result.report.unassigned_ratio)
    Path("out.srt").write_text(sj.to_srt(result), encoding="utf-8")
"""

from __future__ import annotations

from .assign import merge
from .detect import detect_format
from .errors import FormatError, SpeakerJoinError, ThresholdSyntaxError, UnknownFormatError
from .loaders import load_diarization, load_transcript
from .model import (
    AssignedWord,
    Diarization,
    MergeResult,
    Report,
    Segment,
    Transcript,
    Turn,
    Utterance,
    Word,
)
from .report import check_thresholds
from .writers import to_json, to_markdown, to_srt, to_text, to_vtt

__version__ = "0.1.0"

__all__ = [
    "AssignedWord",
    "Diarization",
    "FormatError",
    "MergeResult",
    "Report",
    "Segment",
    "SpeakerJoinError",
    "ThresholdSyntaxError",
    "Transcript",
    "Turn",
    "UnknownFormatError",
    "Utterance",
    "Word",
    "__version__",
    "check_thresholds",
    "detect_format",
    "load_diarization",
    "load_transcript",
    "merge",
    "to_json",
    "to_markdown",
    "to_srt",
    "to_text",
    "to_vtt",
]
