"""AC-3 and AC-4: word-level assignment, segment fallback, and the edge cases."""

import pytest

import speakerjoin as sj
from speakerjoin.model import Segment, Transcript, Word


def one_segment(words, start=None, end=None):
    """A transcript with a single segment built from (text, start, end) tuples."""
    ws = tuple(Word(t, a, b) for t, a, b in words)
    timed = [w for w in ws if w.start is not None]
    seg = Segment(
        start if start is not None else timed[0].start,
        end if end is not None else timed[-1].end,
        " ".join(w.text for w in ws),
        ws,
    )
    return Transcript((seg,), "faster_whisper")


def merged(words, turns, **options):
    return sj.merge(one_segment(words), sj.load_diarization(turns), **options)


# --- AC-3 -------------------------------------------------------------------------------


def test_segment_spanning_two_speakers_splits_into_two_utterances():
    # Hand-made: one STT segment (1.0-1.8) covers the speaker change at 1.5 s.
    tr = sj.load_transcript(
        {
            "segments": [
                {
                    "start": 1.0,
                    "end": 1.8,
                    "text": "hello there",
                    "words": [
                        {"word": "hello", "start": 1.0, "end": 1.4},
                        {"word": "there", "start": 1.4, "end": 1.8},
                    ],
                }
            ]
        }
    )
    di = sj.load_diarization([(0.0, 1.5, "A"), (1.5, 3.0, "B")])
    res = sj.merge(tr, di)
    assert [(u.speaker, u.text) for u in res.utterances] == [("A", "hello"), ("B", "there")]
    # Per segment, the whole line would go to A (0.5 s overlap vs 0.3 s): "there" differs.
    assert res.report.segment_word_disagree == 1
    assert res.report.segments_multi_speaker == 1
    assert res.report.segment_word_disagree_ratio == pytest.approx(0.5)


def test_segment_spanning_in_the_bundled_sample_is_pinned():
    from importlib.resources import files

    base = files("speakerjoin").joinpath("samples")
    res = sj.merge(
        sj.load_transcript(base.joinpath("meeting.whisper.json").read_text(encoding="utf-8")),
        sj.load_diarization(base.joinpath("meeting.rttm").read_text(encoding="utf-8")),
    )
    r = res.report
    assert (r.words_total, r.segment_word_disagree, r.segments_multi_speaker) == (39, 8, 2)
    assert (r.unassigned, r.overlap_words, r.boundary_words, r.words_untimed) == (3, 1, 10, 1)
    assert r.speech_without_words_sec == pytest.approx(1.0)


@pytest.mark.parametrize("name", ["stt.srt", "stt_openai_diarized.json", "stt.vtt"])
def test_fallback_to_segment_level_without_word_timing(fx, name):
    res = sj.merge(sj.load_transcript(fx(name)), sj.load_diarization(fx("diar.rttm")))
    assert [w.speaker for w in res.words] == ["SPEAKER_00", "SPEAKER_01"]
    assert res.words[0].word.text.startswith("hello")
    assert res.report.segment_word_disagree == 0
    assert len(res.utterances) == 2


def test_unit_segment_forces_one_speaker_per_segment(fx):
    tr = sj.load_transcript(fx("stt_faster_whisper.json"))
    di = sj.load_diarization([(0.0, 1.5, "A"), (1.5, 3.0, "B")])
    by_word = sj.merge(tr, di)
    by_segment = sj.merge(tr, di, unit="segment")
    assert [w.speaker for w in by_word.words] == ["A", "B", "B", "B", "B"]
    assert [w.speaker for w in by_segment.words] == ["A", "A", "B", "B", "B"]
    assert by_segment.report.segment_word_disagree == 0  # nothing was assigned per word


# --- AC-4 -------------------------------------------------------------------------------


def test_edge_zero_length_word_is_assigned_via_min_word_dur():
    res = merged([("a", 0.5, 0.9), ("wait", 1.0, 1.0)], [(0.0, 2.0, "A")])
    assert [w.speaker for w in res.words] == ["A", "A"]
    assert [sorted(w.flags) for w in res.words] == [[], ["zero_length"]]
    widened = res.words[1].word
    assert widened.end - widened.start == pytest.approx(0.02)
    assert (widened.start + widened.end) / 2 == pytest.approx(1.0)
    wide = merged([("wait", 1.0, 1.0)], [(0.0, 2.0, "A")], min_word_dur=0.2)
    assert wide.words[0].word.end - wide.words[0].word.start == pytest.approx(0.2)


def test_edge_untimed_word_is_interpolated_between_neighbours(fx):
    res = sj.merge(
        sj.load_transcript(fx("stt_whisperx.json")), sj.load_diarization(fx("diar.rttm"))
    )
    forty_two = res.words[3]
    assert forty_two.word.text == "42"
    assert forty_two.word.start == pytest.approx(2.2)
    assert forty_two.word.end == pytest.approx(2.4)
    assert "interpolated" in forty_two.flags
    assert forty_two.speaker == "SPEAKER_01"
    assert res.report.words_untimed == 1


def test_edge_untimed_run_is_spread_evenly_over_the_segment_bounds():
    seg = Segment(
        1.0,
        4.0,
        "a b c",
        (Word("a", None, None), Word("b", None, None), Word("c", 3.0, 4.0)),
    )
    res = sj.merge(Transcript((seg,), "x"), sj.load_diarization([(0.0, 5.0, "A")]))
    a, b = res.words[0].word, res.words[1].word
    assert (a.start, a.end) == pytest.approx((1.0, 2.0))
    assert (b.start, b.end) == pytest.approx((2.0, 3.0))
    assert all("interpolated" in w.flags for w in res.words[:2])
    assert "interpolated" not in res.words[2].flags


def test_edge_unassigned_and_fill_nearest():
    turns = [(0.0, 2.0, "A"), (6.0, 7.0, "B")]
    plain = merged([("x", 5.0, 5.3)], turns)
    assert plain.words[0].speaker is None
    assert "unassigned" in plain.words[0].flags
    assert plain.report.unassigned == 1
    assert plain.report.unassigned_ratio == 1.0
    assert plain.utterances[0].speaker is None
    filled = merged([("x", 5.0, 5.3)], turns, fill_nearest=True)
    assert filled.words[0].speaker == "B"  # 0.7 s away versus 3.0 s
    assert "filled_nearest" in filled.words[0].flags
    assert "unassigned" not in filled.words[0].flags
    assert (filled.report.filled_nearest, filled.report.unassigned) == (1, 0)
    before = merged([("x", 2.5, 2.6)], turns, fill_nearest=True)
    assert before.words[0].speaker == "A"


def test_edge_overlapped_speech_flags_the_word():
    turns = [(0.0, 2.0, "A"), (1.0, 3.0, "B")]
    res = merged([("solo", 0.2, 0.5), ("in", 1.4, 1.6), ("late", 2.4, 2.8)], turns)
    assert [("overlap" in w.flags) for w in res.words] == [False, True, False]
    assert res.report.overlap_words == 1


def test_edge_boundary_words_use_the_tolerance():
    turns = [(0.0, 2.0, "A"), (2.0, 4.0, "B")]
    words = [
        ("near_start", 0.1, 0.4),
        ("middle", 0.8, 1.2),
        ("across", 1.9, 2.1),
        ("after", 2.5, 2.7),
        ("near_end", 3.7, 3.9),
    ]
    res = merged(words, turns)
    assert [("boundary" in w.flags) for w in res.words] == [True, False, True, False, True]
    assert res.report.boundary_words == 3
    tight = merged(words, turns, tolerance=0.05)
    assert tight.report.boundary_words == 0
    assert merged(words, turns, tolerance=0.11).report.boundary_words == 3


def test_edge_midpoint_and_overlap_strategies_can_disagree():
    turns = [(0.0, 1.6, "A"), (1.0, 1.3, "B"), (1.62, 2.0, "B")]
    word = [("w", 1.0, 2.0)]
    assert merged(word, turns, strategy="overlap").words[0].speaker == "B"  # 0.68 s vs 0.6 s
    assert merged(word, turns, strategy="midpoint").words[0].speaker == "A"  # 1.5 s is in A only


def test_edge_midpoint_in_gap_is_unassigned_unless_filled():
    turns = [(0.0, 1.0, "A"), (3.0, 4.0, "B")]
    word = [("w", 1.5, 2.0)]
    assert merged(word, turns, strategy="midpoint").words[0].speaker is None
    assert merged(word, turns, strategy="midpoint", fill_nearest=True).words[0].speaker == "A"


def test_edge_no_turns_leaves_everything_unassigned():
    assert merged([("a", 0.0, 1.0)], []).report.unassigned == 1
    assert merged([("a", 0.0, 1.0)], [], fill_nearest=True).report.unassigned == 1


def test_edge_invalid_options_raise_value_error():
    tr = one_segment([("a", 0.0, 1.0)])
    di = sj.load_diarization([(0.0, 1.0, "A")])
    for kwargs in ({"strategy": "x"}, {"unit": "x"}, {"min_word_dur": 0}, {"tolerance": -1}):
        with pytest.raises(ValueError):
            sj.merge(tr, di, **kwargs)


def test_edge_speaker_changes_and_shares():
    res = merged(
        [("a", 0.1, 0.4), ("b", 1.1, 1.4), ("c", 1.5, 1.9), ("d", 0.5, 0.6)],
        [(0.0, 1.0, "A"), (1.0, 2.0, "B")],
    )
    assert res.report.speaker_changes == 2
    assert res.report.word_share == {"A": 0.5, "B": 0.5}
    assert res.report.dominant_speaker_share == 0.5
    assert res.report.talk_time == {"A": 1.0, "B": 1.0}
