"""Merge the bundled synthetic sample from Python and print the quality numbers.

Run from the repository root:  uv run python examples/merge_sample.py
"""

from importlib.resources import files

import speakerjoin as sj

samples = files("speakerjoin").joinpath("samples")
transcript = sj.load_transcript(
    samples.joinpath("meeting.whisper.json").read_text(encoding="utf-8")
)
diarization = sj.load_diarization(samples.joinpath("meeting.rttm").read_text(encoding="utf-8"))

result = sj.merge(transcript, diarization, strategy="overlap", fill_nearest=False)

report = result.report
print(f"words: {report.words_total}, unassigned: {report.unassigned}")
print(f"a per-segment assignment would differ on {report.segment_word_disagree} words")

# Rename speakers on the way out; the same call works for to_vtt, to_json, to_markdown, to_text.
print(sj.to_srt(result, speaker_map={"SPEAKER_00": "Alice"}).split("\n\n")[0])

# Gate a pipeline on quality (an empty list means every threshold passed).
print(sj.check_thresholds(report, ["unassigned_ratio>0.05"]))
