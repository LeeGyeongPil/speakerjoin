"""AC-7: CLI merge / report / demo behaviour and exit codes."""

import json

import pytest

import speakerjoin as sj
from speakerjoin.cli import main


@pytest.fixture
def args(fx):
    """Common positional arguments: faster-whisper transcript plus the RTTM."""
    return [str(fx("stt_faster_whisper.json")), "--diar", str(fx("diar.rttm"))]


@pytest.fixture
def partial_rttm(tmp_path):
    """Diarization that only covers the first 1.9 s, leaving 3 of 5 words unassigned."""
    path = tmp_path / "partial.rttm"
    path.write_text("SPEAKER clip 1 0.00 1.90 <NA> <NA> SPEAKER_00 <NA> <NA>\n")
    return path


def test_merge_writes_output_and_report(args, tmp_path, capsys):
    out, rep = tmp_path / "out.vtt", tmp_path / "quality.json"
    code = main(
        ["merge", *args, "-o", str(out), "--report", str(rep), "--speaker-map", "SPEAKER_00=Alice"]
    )
    assert code == 0
    assert out.read_text().startswith("WEBVTT")
    assert "<v Alice>hello there" in out.read_text()
    doc = json.loads(rep.read_text())
    assert doc["schema"] == 1
    assert doc["report"]["words_total"] == 5
    assert doc["options"]["strategy"] == "overlap"
    assert "5 words" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("suffix", "needle"),
    [
        (".srt", "[SPEAKER_00] hello there"),
        (".json", '"schema": 1'),
        (".md", "**SPEAKER_00**"),
        (".txt", "SPEAKER_00: hello there"),
    ],
)
def test_merge_infers_the_format_from_the_extension(args, tmp_path, suffix, needle):
    out = tmp_path / f"out{suffix}"
    assert main(["merge", *args, "-o", str(out)]) == 0
    assert needle in out.read_text()


def test_merge_prints_to_stdout_without_output_file(args, capsys):
    assert main(["merge", *args, "--format", "txt"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["SPEAKER_00: hello there", "SPEAKER_01: how are you"]


def test_report_fail_on_exits_1_and_names_the_metric(args, fx, partial_rttm, capsys):
    stt = args[0]
    code = main(["report", stt, "--diar", str(partial_rttm), "--fail-on", "unassigned_ratio>0.05"])
    out = capsys.readouterr().out
    assert code == 1
    assert "Threshold exceeded: unassigned_ratio=0.6 > 0.05" in out
    assert "words_total" in out  # the table is printed before the verdict


def test_report_fail_on_passes_with_exit_0(args, capsys):
    code = main(["report", *args, "--fail-on", "unassigned_ratio>0.05",
                 "--fail-on", "segment_word_disagree_ratio>=0.5"])  # fmt: skip
    assert code == 0
    assert "Threshold exceeded" not in capsys.readouterr().out


def test_report_several_thresholds_list_every_failure(args, partial_rttm, capsys):
    code = main(["report", args[0], "--diar", str(partial_rttm), "--fail-on", "unassigned>=3",
                 "--fail-on", "words_total<10", "--fail-on", "overlap_words>0"])  # fmt: skip
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("Threshold")]
    assert code == 1
    assert len(lines) == 2


@pytest.mark.parametrize("expr", ["unassigned_ratio", "unassigned_ratio>>1", "nope>1", "x>abc"])
def test_malformed_threshold_exits_2(args, capsys, expr):
    code = main(["report", *args, "--fail-on", expr])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""  # rejected before any work
    assert captured.err.startswith("error: Invalid --fail-on")


def test_check_thresholds_api(args, fx):
    res = sj.merge(
        sj.load_transcript(fx("stt_faster_whisper.json")), sj.load_diarization(fx("diar.rttm"))
    )
    assert sj.check_thresholds(res.report, ["words_total>=5"]) == ["words_total=5 >= 5"]
    assert sj.check_thresholds(res.report, ["words_total>5"]) == []
    with pytest.raises(sj.ThresholdSyntaxError, match="Available"):
        sj.check_thresholds(res.report, ["bogus>1"])


def test_report_json_output(args, capsys):
    assert main(["report", *args, "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["report"]["words_total"] == 5


def test_demo_states_synthetic_and_writes_four_files(tmp_path, capsys):
    out = tmp_path / "demo-out"
    code = main(["demo", "--out", str(out)])
    text = capsys.readouterr().out
    assert code == 0
    assert text.splitlines()[0] == "NOTE: synthetic practice sample, not a real recording."
    row = next(ln for ln in text.splitlines() if ln.startswith("segment_word_disagree "))
    assert row.split()[1] == "8"
    assert "8 of 39 words" in text
    assert sorted(p.name for p in out.iterdir()) == ["demo.json", "demo.md", "demo.srt", "demo.vtt"]
    assert (out / "demo.vtt").read_text().startswith("WEBVTT")
    assert json.loads((out / "demo.json").read_text())["report"]["segment_word_disagree"] == 8


def test_input_errors_exit_2(args, tmp_path, capsys):
    assert main(["merge", args[0], "--diar", str(tmp_path / "missing.rttm")]) == 2
    assert "Cannot read" in capsys.readouterr().err
    assert main(["merge", *args, "--speaker-map", "oops"]) == 2
    assert "OLD=NEW" in capsys.readouterr().err
    assert main(["merge", *args, "-o", str(tmp_path / "out.docx")]) == 2
    assert "--format" in capsys.readouterr().err
    assert main(["merge", *args, "-o", str(tmp_path / "no-such-dir" / "out.srt")]) == 2
    assert "Cannot write" in capsys.readouterr().err
    assert main(["merge", *args, "--tolerance", "-1"]) == 2
    assert "tolerance" in capsys.readouterr().err


def test_usage_errors_exit_2(capsys):
    assert main(["merge"]) == 2
    assert "error: Invalid usage" in capsys.readouterr().err
    assert main([]) == 2
    assert main(["--version"]) == 0


def test_formats_command_lists_everything(capsys):
    assert main(["formats"]) == 0
    out = capsys.readouterr().out
    for name in ("openai_verbose", "assemblyai", "rttm", "pyannoteai", "vtt"):
        assert name in out
