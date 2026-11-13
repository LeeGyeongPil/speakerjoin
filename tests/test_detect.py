"""AC-2: format detection from the shape of the data."""

import pytest

import speakerjoin as sj
from speakerjoin.cli import main
from speakerjoin.detect import ALL_FORMATS
from speakerjoin.errors import UnknownFormatError

CASES = [
    ("stt_openai_verbose.json", "openai_verbose"),
    ("stt_openai_diarized.json", "openai_diarized"),
    ("stt_faster_whisper.json", "faster_whisper"),
    ("stt_whisperx.json", "whisperx"),
    ("stt_deepgram.json", "deepgram"),
    ("stt_assemblyai.json", "assemblyai"),
    ("stt.srt", "srt"),
    ("stt.vtt", "vtt"),
    ("diar.rttm", "rttm"),
    ("diar_pyannoteai.json", "pyannoteai"),
    ("diar.json", "json"),
]


@pytest.mark.parametrize(("name", "expected"), CASES)
def test_detect_every_fixture(fx, name, expected):
    from speakerjoin.readers import read_source

    data, _label = read_source(fx(name))
    assert sj.detect_format(data) == expected


def test_all_eleven_formats_are_covered():
    assert {expected for _n, expected in CASES} == set(ALL_FORMATS)
    assert len(ALL_FORMATS) == 11


def test_whisperx_without_word_segments_is_recognised_by_scores():
    data = {
        "segments": [
            {
                "start": 0,
                "end": 1,
                "text": "a",
                "words": [{"word": "a", "start": 0, "end": 1, "score": 0.5}],
            }
        ]
    }
    assert sj.detect_format(data) == "whisperx"


def test_unknown_json_lists_supported_formats():
    with pytest.raises(UnknownFormatError) as info:
        sj.detect_format({"hello": "world"})
    for name in ALL_FORMATS:
        assert name in str(info.value)
    assert info.value.supported == ALL_FORMATS


def test_forcing_a_format_skips_detection(fx):
    tr = sj.load_transcript({"segments": []}, format="faster_whisper")
    assert tr.source_format == "faster_whisper"
    with pytest.raises(UnknownFormatError, match="format='nope'"):
        sj.load_transcript(fx("stt.srt"), format="nope")


def test_cli_unknown_format_exits_2_with_one_line(tmp_path, capsys, fx):
    mystery = tmp_path / "mystery.json"
    mystery.write_text('{"hello": "world"}')
    code = main(["report", str(mystery), "--diar", str(fx("diar.rttm"))])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    lines = captured.err.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("error: ")
    assert "faster_whisper" in lines[0]
    assert "--stt-format" in lines[0]
