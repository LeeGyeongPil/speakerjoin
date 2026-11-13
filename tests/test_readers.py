"""AC-1: every input format is read into the shared model with the right units."""

import pytest

import speakerjoin as sj
from speakerjoin.errors import FormatError

STT_CASES = [
    ("stt_openai_verbose.json", "openai_verbose", 5),
    ("stt_openai_diarized.json", "openai_diarized", 0),
    ("stt_faster_whisper.json", "faster_whisper", 5),
    ("stt_whisperx.json", "whisperx", 5),
    ("stt_deepgram.json", "deepgram", 5),
    ("stt_assemblyai.json", "assemblyai", 5),
    ("stt.srt", "srt", 0),
    ("stt.vtt", "vtt", 0),
]


@pytest.mark.parametrize(("name", "fmt", "n_words"), STT_CASES)
def test_every_stt_format_loads(fx, name, fmt, n_words):
    tr = sj.load_transcript(fx(name))
    assert tr.source_format == fmt
    assert len(tr.words) == n_words
    assert len(tr.segments) >= 1


@pytest.mark.parametrize(
    ("name", "fmt"),
    [("diar.rttm", "rttm"), ("diar.json", "json"), ("diar_pyannoteai.json", "pyannoteai")],
)
def test_every_diarization_format_loads(fx, name, fmt):
    di = sj.load_diarization(fx(name))
    assert di.source_format == fmt
    assert [t.speaker for t in di.turns] == ["SPEAKER_00", "SPEAKER_01"]


def test_assemblyai_milliseconds_become_seconds(fx):
    words = sj.load_transcript(fx("stt_assemblyai.json")).words
    assert words[0].start == 1.52
    assert words[0].end == 1.9
    assert words[-1].end == 3.3


def test_rttm_columns_are_start_and_duration():
    text = "SPEAKER f 1 3.10 0.80 <NA> <NA> A <NA> <NA>\n"
    (turn,) = sj.load_diarization(text).turns
    assert turn.start == pytest.approx(3.10)
    assert turn.end == pytest.approx(3.90)
    assert turn.speaker == "A"


def test_openai_top_level_words_are_redistributed_by_time(fx):
    tr = sj.load_transcript(fx("stt_openai_verbose.json"))
    assert [[w.text for w in s.words] for s in tr.segments] == [
        ["hello", "there"],
        ["how", "are", "you"],
    ]


def test_openai_word_in_a_gap_joins_the_nearer_segment():
    data = {
        "segments": [
            {"id": 0, "seek": 0, "start": 0.0, "end": 1.0, "text": "a"},
            {"id": 1, "seek": 0, "start": 2.0, "end": 3.0, "text": "b"},
        ],
        "words": [
            {"word": "a", "start": 0.0, "end": 1.0},
            {"word": "x", "start": 1.6, "end": 1.8},
            {"word": "b", "start": 2.0, "end": 3.0},
        ],
    }
    tr = sj.load_transcript(data)
    assert [[w.text for w in s.words] for s in tr.segments] == [["a"], ["x", "b"]]


def test_faster_whisper_leading_spaces_do_not_double(fx):
    tr = sj.load_transcript(fx("stt_faster_whisper.json"))
    assert [w.text for w in tr.words] == ["hello", "there", "how", "are", "you"]
    assert " ".join(w.text for w in tr.words) == "hello there how are you"
    assert "  " not in " ".join(s.text for s in tr.segments)
    assert tr.words[0].confidence == pytest.approx(0.98)


def test_whisperx_word_without_start_is_kept(fx):
    tr = sj.load_transcript(fx("stt_whisperx.json"))
    untimed = [w for w in tr.words if w.start is None]
    assert [w.text for w in untimed] == ["42"]
    assert len(tr.words) == 5


def test_deepgram_prefers_punctuated_word(fx):
    tr = sj.load_transcript(fx("stt_deepgram.json"))
    assert [w.text for w in tr.words] == ["Hello", "there.", "How", "are", "you?"]
    assert tr.words[2].speaker == "1"
    assert [len(s.words) for s in tr.segments] == [2, 3]  # split after "there."


def test_assemblyai_utterances_become_segments():
    data = {
        "utterances": [
            {
                "speaker": "A",
                "start": 100,
                "end": 900,
                "text": "hi there",
                "words": [
                    {"text": "hi", "start": 100, "end": 400},
                    {"text": "there", "start": 500, "end": 900},
                ],
            }
        ]
    }
    tr = sj.load_transcript(data)
    assert tr.segments[0].speaker == "A"
    assert tr.segments[0].start == pytest.approx(0.1)
    assert tr.words[1].start == pytest.approx(0.5)


def test_openai_diarized_keeps_segment_speakers(fx):
    tr = sj.load_transcript(fx("stt_openai_diarized.json"))
    assert [s.speaker for s in tr.segments] == ["A", "B"]
    assert all(not s.words for s in tr.segments)


def test_srt_joins_lines_and_vtt_reads_voice_tags(fx):
    srt = sj.load_transcript(fx("stt.srt"))
    assert [s.text for s in srt.segments] == ["hello there", "how are you"]
    assert srt.segments[1].end == pytest.approx(2.7)
    vtt = sj.load_transcript(fx("stt.vtt"))
    assert [s.speaker for s in vtt.segments] == ["Alice", "Bob"]
    assert vtt.segments[1].text == "how & you"  # entity unescaped, <i> tag stripped
    assert vtt.segments[1].start == pytest.approx(2.0)  # MM:SS.mmm without hours


def test_pyannoteai_prefers_exclusive_diarization(fx):
    exclusive = sj.load_diarization(fx("diar_pyannoteai.json"))
    assert exclusive.exclusive is True
    assert exclusive.turns[0].end == 1.9
    regular = sj.load_diarization(fx("diar_pyannoteai.json"), prefer_exclusive=False)
    assert regular.exclusive is False
    assert regular.turns[0].end == 2.0


def test_rttm_with_several_file_ids_needs_file_id(fx):
    with pytest.raises(FormatError, match="file_id"):
        sj.load_diarization(fx("diar_multi.rttm"))
    di = sj.load_diarization(fx("diar_multi.rttm"), file_id="two")
    assert [t.speaker for t in di.turns] == ["SPEAKER_01"]
    with pytest.raises(FormatError, match="no turns for file ID 'nope'"):
        sj.load_diarization(fx("diar_multi.rttm"), file_id="nope")


def test_python_objects_tuples_and_annotation_duck_typing():
    di = sj.load_diarization([(2.0, 3.0, "B"), (0.0, 2.0, "A")])
    assert [(t.start, t.end, t.speaker) for t in di.turns] == [(0.0, 2.0, "A"), (2.0, 3.0, "B")]

    class Seg:
        def __init__(self, start, end):
            self.start, self.end = start, end

    class FakeAnnotation:
        def itertracks(self, yield_label=False):
            assert yield_label is True
            yield Seg(0.5, 1.5), "t0", "SPEAKER_00"
            yield Seg(1.5, 2.5), "t1", "SPEAKER_01"

    di = sj.load_diarization(FakeAnnotation())
    assert di.source_format == "annotation"
    assert [t.speaker for t in di.turns] == ["SPEAKER_00", "SPEAKER_01"]


def test_error_messages_say_where_and_how_to_fix(tmp_path):
    bad = tmp_path / "bad.rttm"
    bad.write_text("SPEAKER f 1 0.0 1.0 <NA> <NA> A <NA> <NA>\nSPEAKER f 1 1.0 oops <NA> <NA> A\n")
    with pytest.raises(FormatError, match=r"bad\.rttm:2.*duration.*'oops'"):
        sj.load_diarization(bad)
    with pytest.raises(FormatError, match="Cannot read"):
        sj.load_transcript(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text('{"segments": [')
    with pytest.raises(FormatError, match="invalid JSON at line 1"):
        sj.load_transcript(broken)
    with pytest.raises(FormatError, match="looks like a diarization"):
        sj.load_transcript(tmp_path / "bad.rttm")
    with pytest.raises(FormatError, match="end .* before start"):
        sj.load_diarization([(2.0, 1.0, "A")])
    with pytest.raises(FormatError, match="expected a number"):
        sj.load_transcript({"segments": [{"start": "x", "end": 1, "text": "a", "words": []}]})
