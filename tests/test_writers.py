"""AC-6: writers match golden files byte for byte; cue splitting rules; VTT round trip."""

import json
from pathlib import Path

import pytest

import speakerjoin as sj
from speakerjoin.model import Segment, Transcript, Word

NAMES = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}


@pytest.fixture
def basic(fx):
    return sj.merge(
        sj.load_transcript(fx("stt_assemblyai.json")), sj.load_diarization(fx("diar.rttm"))
    )


def golden(name):
    return (Path(__file__).parent / "golden" / name).read_bytes()


def test_srt_matches_golden(basic):
    out = sj.to_srt(basic)
    assert out.encode() == golden("basic.srt")
    assert "00:00:01,520 --> 00:00:01,900" in out  # comma, milliseconds from 1520 ms
    assert "[SPEAKER_00] hello" in out


def test_vtt_matches_golden_and_applies_speaker_map(basic):
    out = sj.to_vtt(basic, speaker_map=NAMES)
    assert out.encode() == golden("basic.vtt")
    assert out.startswith("WEBVTT\n")
    assert "<v Alice>hello" in out
    assert "<v UNKNOWN>" in out  # unmapped / unassigned labels pass through


def test_json_matches_golden_and_has_flags(basic):
    out = sj.to_json(basic)
    assert out.encode() == golden("basic.json")
    doc = json.loads(out)
    assert doc["schema"] == 1
    assert doc["report"]["unassigned"] == 1
    last = doc["words"][-1]
    assert last["speaker"] is None
    assert "unassigned" in last["flags"]


def test_markdown_and_text_match_golden(basic):
    assert sj.to_markdown(basic, speaker_map=NAMES).encode() == golden("basic.md")
    assert sj.to_text(basic, speaker_map=NAMES).encode() == golden("basic.txt")
    assert sj.to_markdown(basic, title="Notes").startswith("# Notes\n")


def test_a_speaker_change_always_starts_a_new_cue(basic):
    cues = sj.to_srt(basic).strip().split("\n\n")
    assert len(cues) == 3
    assert [len(c.splitlines()) for c in cues] == [3, 3, 3]


def make_result(words, turns):
    seg = Segment(words[0][1], words[-1][2], "x", tuple(Word(*w) for w in words))
    return sj.merge(Transcript((seg,), "x"), sj.load_diarization(turns))


def test_cue_splits_after_42_characters():
    words = [("abcdefghij", i * 0.5, i * 0.5 + 0.4) for i in range(5)]
    res = make_result(words, [(0.0, 9.0, "A")])
    cues = sj.to_srt(res).strip().split("\n\n")
    assert [c.splitlines()[2] for c in cues] == [
        "[A] abcdefghij abcdefghij abcdefghij",
        "[A] abcdefghij abcdefghij",
    ]
    # the first cue holds 32 characters of text: a fourth word would make it 43 > 42
    assert len("abcdefghij abcdefghij abcdefghij") == 32
    assert len(sj.to_srt(res, max_chars=100).strip().split("\n\n")) == 1


def test_cue_splits_after_7_seconds():
    words = [("a", float(i), i + 1.0) for i in range(8)]
    res = make_result(words, [(0.0, 20.0, "A")])
    cues = sj.to_srt(res).strip().split("\n\n")
    assert len(cues) == 2
    assert cues[0].splitlines()[1] == "00:00:00,000 --> 00:00:07,000"
    assert cues[1].splitlines()[1] == "00:00:07,000 --> 00:00:08,000"
    assert len(sj.to_srt(res, max_duration=60.0).strip().split("\n\n")) == 1


def test_vtt_round_trip_keeps_the_speaker_of_every_cue(basic):
    text = sj.to_vtt(basic, speaker_map=NAMES)
    again = sj.load_transcript(text)
    assert again.source_format == "vtt"
    assert [s.speaker for s in again.segments] == ["Alice", "Bob", "UNKNOWN"]
    assert [s.text for s in again.segments] == ["hello", "there how are", "you?"]
    assert again.segments[0].start == pytest.approx(1.52)


def test_vtt_escapes_markup_characters():
    res = make_result([("a<b&c>", 0.0, 1.0)], [(0.0, 2.0, "A")])
    out = sj.to_vtt(res)
    assert "<v A>a&lt;b&amp;c&gt;" in out
    assert sj.load_transcript(out).segments[0].text == "a<b&c>"


def test_timestamps_round_to_milliseconds_and_never_go_negative():
    res = make_result([("a", 3661.0004, 3662.0006)], [(3600.0, 3700.0, "A")])
    assert "01:01:01,000 --> 01:01:02,001" in sj.to_srt(res)
