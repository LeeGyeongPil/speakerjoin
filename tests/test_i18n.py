"""AC-8: two display languages, identical message keys, documented precedence."""

import json
import re
from pathlib import Path

import pytest

from speakerjoin.cli import main
from speakerjoin.i18n import MESSAGES, resolve_lang, t

HANGUL = re.compile("[가-힣]")


def test_message_tables_have_identical_keys_and_placeholders():
    assert set(MESSAGES["en"]) == set(MESSAGES["ko"])
    field = re.compile(r"\{(\w+)")
    for key in MESSAGES["en"]:
        assert set(field.findall(MESSAGES["en"][key])) == set(field.findall(MESSAGES["ko"][key])), (
            key
        )


def test_english_messages_have_no_hangul_and_korean_ones_have_it():
    for key, text in MESSAGES["en"].items():
        assert not HANGUL.search(text), key
    # every Korean message except pure technical strings contains Hangul
    assert sum(bool(HANGUL.search(v)) for v in MESSAGES["ko"].values()) >= len(MESSAGES["ko"]) - 2


@pytest.mark.parametrize(
    ("argv", "env", "expected"),
    [
        ([], {}, "en"),
        (["--lang", "ko"], {}, "ko"),
        (["merge", "--lang=ko"], {}, "ko"),
        (["--lang", "en"], {"SPEAKERJOIN_LANG": "ko", "LANG": "ko_KR.UTF-8"}, "en"),
        ([], {"SPEAKERJOIN_LANG": "ko", "LC_ALL": "en_US.UTF-8"}, "ko"),
        ([], {"SPEAKERJOIN_LANG": "en", "LC_ALL": "ko_KR.UTF-8"}, "en"),
        ([], {"LC_ALL": "ko_KR.UTF-8", "LC_MESSAGES": "en_US", "LANG": "en_US"}, "ko"),
        ([], {"LC_MESSAGES": "ko_KR", "LANG": "en_US.UTF-8"}, "ko"),
        ([], {"LANG": "ko_KR.UTF-8"}, "ko"),
        ([], {"LANG": "fr_FR.UTF-8"}, "en"),
        ([], {"LANG": "C"}, "en"),
        (["--lang", "fr"], {"LANG": "ko_KR.UTF-8"}, "ko"),  # invalid value is ignored here
        ([], {"SPEAKERJOIN_LANG": "", "LANG": "ko"}, "ko"),
    ],
)
def test_language_precedence(argv, env, expected):
    assert resolve_lang(argv, env) == expected


def test_t_fills_placeholders():
    assert t("en", "demo.wrote", path="x") == "Wrote x"
    assert t("ko", "demo.wrote", path="x") == "씀: x"


def test_help_is_translated(capsys):
    assert main(["--lang", "ko", "--help"]) == 0
    ko = capsys.readouterr().out
    assert "받아쓰기" in ko
    assert main(["--lang", "en", "--help"]) == 0
    en = capsys.readouterr().out
    assert "Join speech-to-text output" in en
    assert not HANGUL.search(en)
    assert main(["merge", "--lang", "ko", "--help"]) == 0
    assert "화자 분리 결과" in capsys.readouterr().out


def test_demo_table_switches_language(tmp_path, capsys):
    assert main(["demo", "--lang", "ko", "--out", str(tmp_path / "a")]) == 0
    ko = capsys.readouterr().out
    assert main(["demo", "--lang", "en", "--out", str(tmp_path / "b")]) == 0
    en = capsys.readouterr().out
    assert "연습용 합성 샘플" in ko.splitlines()[0]
    assert "synthetic practice sample" in en.splitlines()[0]
    assert "정렬 품질" in ko and "Alignment quality" in en
    # metric names (used by --fail-on) stay English in both
    assert "segment_word_disagree" in ko and "segment_word_disagree" in en
    assert (tmp_path / "a" / "demo.md").read_text().startswith("# 대본")
    assert (tmp_path / "b" / "demo.md").read_text().startswith("# Transcript")


def test_environment_variable_selects_language(monkeypatch, capsys):
    monkeypatch.setenv("SPEAKERJOIN_LANG", "ko")
    assert main(["formats"]) == 0
    assert "지원 형식" in capsys.readouterr().out
    assert main(["formats", "--lang", "en"]) == 0  # the flag beats the variable
    assert "Supported formats" in capsys.readouterr().out
    monkeypatch.setenv("SPEAKERJOIN_LANG", "en")
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    assert main(["formats"]) == 0
    assert "Supported formats" in capsys.readouterr().out


def test_error_messages_are_translated(tmp_path, fx, capsys):
    mystery = tmp_path / "m.json"
    mystery.write_text("{}")
    base = ["report", str(mystery), "--diar", str(fx("diar.rttm"))]
    assert main([*base, "--lang", "ko"]) == 2
    ko = capsys.readouterr().err
    assert ko.startswith("오류: ") and "지원 형식" in ko
    assert main([*base, "--lang", "en"]) == 2
    en = capsys.readouterr().err
    assert en.startswith("error: ") and "Supported:" in en
    good = ["report", str(fx("stt.srt")), "--diar", str(fx("diar.rttm"))]
    assert main([*good, "--fail-on", "zzz>1", "--lang", "ko"]) == 2
    assert "--fail-on 식이 올바르지 않습니다" in capsys.readouterr().err
    assert main(["merge", "--lang", "ko"]) == 2
    assert "사용법이 올바르지 않습니다" in capsys.readouterr().err


def test_json_report_keys_do_not_depend_on_language(tmp_path, fx):
    docs = []
    for lang in ("en", "ko"):
        out = tmp_path / f"{lang}.json"
        assert main(["merge", str(fx("stt.srt")), "--diar", str(fx("diar.rttm")),
                     "--report", str(out), "--lang", lang]) == 0  # fmt: skip
        docs.append(json.loads(out.read_text()))
    assert docs[0] == docs[1]
    assert "unassigned_ratio" in docs[0]["report"]


# --- every user-visible error path is translated (AC-8) ------------------------------------

SRC = Path(__file__).resolve().parent.parent / "src" / "speakerjoin"


def _write(path, text, mode="w"):
    path.write_text(text, encoding="utf-8")
    return str(path)


def _cases(tmp_path, fx):
    stt, rttm = str(fx("stt.srt")), str(fx("diar.rttm"))
    empty = _write(tmp_path / "empty.json", "  \n")
    bad_bytes = tmp_path / "bad.json"
    bad_bytes.write_bytes(b"\xff\xfe\x00bad")
    broken = _write(tmp_path / "broken.json", '{"segments": [')
    bad_srt = _write(tmp_path / "bad.srt", "1\nhello world\n")
    bad_time = _write(tmp_path / "time.srt", "1\n00:00:01 --> soon\nhi\n")
    turns = _write(tmp_path / "turns.json", '{"turns": 5}')
    turn_item = _write(tmp_path / "turn_item.json", '{"turns": [5]}')
    no_end = _write(tmp_path / "no_end.json", '[{"start": 1, "speaker": "A"}]')
    backwards = _write(tmp_path / "back.json", '[{"start": 2, "end": 1, "speaker": "A"}]')
    nospeaker = _write(tmp_path / "nospk.json", '[{"start": 1, "end": 2}]')
    junk_num = _write(tmp_path / "junk.json", '[{"start": "x", "end": 2, "speaker": "A"}]')
    short_rttm = _write(tmp_path / "short.rttm", "SPEAKER f 1 0.0 1.0 A\n")
    nan_rttm = _write(tmp_path / "nan.rttm", "SPEAKER f 1 x y <NA> <NA> A <NA> <NA>\n")
    neg_rttm = _write(tmp_path / "neg.rttm", "SPEAKER f 1 1.0 -1.0 <NA> <NA> A <NA> <NA>\n")
    multi = str(fx("diar_multi.rttm"))
    pyannoteai_bad = _write(tmp_path / "pa.json", '{"output": {"x": 1}, "jobId": "j"}')
    deepgram_bad = _write(tmp_path / "dg.json", '{"results": {"channels": []}}')
    stt_words = _write(tmp_path / "w.json", '{"words": 5, "segments": []}')
    seg_nums = _write(
        tmp_path / "seg.json", '{"segments": [{"text": "a"}], "language": "en", "duration": 1}'
    )
    m = ["merge", stt, "--diar", rttm]
    return {
        "not_found": ["merge", str(tmp_path / "nope.json"), "--diar", rttm],
        "is_directory": ["merge", str(tmp_path), "--diar", rttm],
        "not_utf8": ["merge", str(bad_bytes), "--diar", rttm],
        "empty": ["merge", empty, "--diar", rttm],
        "bad_json": ["merge", broken, "--diar", rttm],
        "wrong_role_diar": ["merge", rttm, "--diar", rttm],
        "wrong_role_stt": ["merge", stt, "--diar", stt],
        "sub_no_timing": ["merge", bad_srt, "--diar", rttm],
        "sub_bad_timing": ["merge", bad_time, "--diar", rttm],
        "json_shape": ["merge", stt, "--diar", turns],
        "turn_object": ["merge", stt, "--diar", turn_item],
        "start_end_required": ["merge", stt, "--diar", no_end],
        "end_before_start": ["merge", stt, "--diar", backwards],
        "speaker_missing": ["merge", stt, "--diar", nospeaker],
        "not_number": ["merge", stt, "--diar", junk_num],
        "rttm_fields": ["merge", stt, "--diar", short_rttm],
        "rttm_numbers": ["merge", stt, "--diar", nan_rttm],
        "rttm_negative_duration": ["merge", stt, "--diar", neg_rttm],
        "rttm_several_ids": ["merge", stt, "--diar", multi],
        "rttm_no_file_id": ["merge", stt, "--diar", multi, "--file-id", "zzz"],
        "pyannoteai_no_list": [
            "merge",
            stt,
            "--diar",
            pyannoteai_bad,
            "--diar-format",
            "pyannoteai",
        ],
        "deepgram_shape": ["merge", deepgram_bad, "--stt-format", "deepgram", "--diar", rttm],
        "expected_list": ["merge", stt_words, "--stt-format", "openai_verbose", "--diar", rttm],
        "segment_needs_numbers": [
            "merge",
            seg_nums,
            "--stt-format",
            "openai_verbose",
            "--diar",
            rttm,
        ],
        "threshold_syntax": ["report", stt, "--diar", rttm, "--fail-on", "oops"],
        "threshold_metric": ["report", stt, "--diar", rttm, "--fail-on", "nosuch>1"],
        "opt_tolerance": [*m, "--tolerance", "-1"],
        "opt_min_word_dur": [*m, "--min-word-dur", "0"],
        "speaker_map": [*m, "--speaker-map", "oops"],
        "unknown_output": [*m, "-o", str(tmp_path / "x.dat")],
        "write": [*m, "-o", str(tmp_path / "no" / "dir" / "x.srt")],
        "argp_invalid_choice": [*m, "--format", "pdf"],
        "argp_invalid_value": [*m, "--tolerance", "abc"],
        "argp_required": ["merge", stt],
        "argp_expected_one": ["merge", stt, "--diar"],
        "argp_unrecognized": [*m, "--bogus"],
        "unknown_format": ["merge", _write(tmp_path / "m.json", "{}"), "--diar", rttm],
    }


CASE_NAMES = [
    "not_found", "is_directory", "not_utf8", "empty", "bad_json", "wrong_role_diar",
    "wrong_role_stt", "sub_no_timing", "sub_bad_timing", "json_shape", "turn_object",
    "start_end_required", "end_before_start", "speaker_missing", "not_number", "rttm_fields",
    "rttm_numbers", "rttm_negative_duration", "rttm_several_ids", "rttm_no_file_id",
    "pyannoteai_no_list", "deepgram_shape", "expected_list", "segment_needs_numbers",
    "threshold_syntax", "threshold_metric", "opt_tolerance", "opt_min_word_dur", "speaker_map",
    "unknown_output", "write", "argp_invalid_choice", "argp_invalid_value", "argp_required",
    "argp_expected_one", "argp_unrecognized", "unknown_format",
]  # fmt: skip


@pytest.mark.parametrize("name", CASE_NAMES)
def test_every_error_path_is_translated(name, tmp_path, fx, capsys):
    argv = _cases(tmp_path, fx)[name]
    assert main([*argv, "--lang", "ko"]) == 2
    ko = capsys.readouterr().err.strip().splitlines()[-1]
    assert main([*argv, "--lang", "en"]) == 2
    en = capsys.readouterr().err.strip().splitlines()[-1]
    assert ko.startswith("오류: ") and en.startswith("error: ")
    # Korean output carries a Korean sentence ...
    assert HANGUL.search(ko.removeprefix("오류: ")), ko
    # ... and no fixed English wording from any English template leaks into it
    for key, template in MESSAGES["en"].items():
        if not key.startswith(("err.", "error.", "argp.")):
            continue
        for piece in re.split(r"\{[^}]*\}", template):
            if len(piece.split()) >= 3:
                assert piece.strip() not in ko, (name, key, ko)
    # the English run stays English except for echoed user data
    assert en.startswith("error: ")


def test_ko_rendering_equals_message_table(tmp_path, fx, capsys):
    argv = _cases(tmp_path, fx)["threshold_metric"]
    assert main([*argv, "--lang", "ko"]) == 2
    ko = capsys.readouterr().err.strip()
    detail = t(
        "ko",
        "err.threshold_metric",
        name="nosuch",
        expr="nosuch>1",
        available=ko.split("사용 가능: ")[1].rstrip("."),
    )
    assert ko == f"오류: {t('ko', 'error.threshold', detail=detail)}"


def test_every_error_key_used_in_source_exists_in_both_tables():
    used = set()
    for path in SRC.rglob("*.py"):
        used |= set(
            re.findall(
                r"(?:FormatError|ThresholdSyntaxError|ConfigError)\(\s*\"(\w+)\"",
                path.read_text(encoding="utf-8"),
            )
        )
    assert len(used) >= 30
    for lang in ("en", "ko"):
        missing = {k for k in used if f"err.{k}" not in MESSAGES[lang]}
        assert not missing, (lang, missing)


def test_library_errors_stay_english_and_carry_a_key(tmp_path):
    import speakerjoin as sj

    with pytest.raises(sj.FormatError, match="Check that the path exists") as info:
        sj.load_transcript(tmp_path / "missing.json")
    assert info.value.key == "not_found"
    assert not HANGUL.search(str(info.value))
    with pytest.raises(ValueError, match="tolerance must not be negative"):
        sj.merge(sj.Transcript((), "x"), sj.Diarization((), "x"), tolerance=-1)


def test_korean_table_columns_line_up(tmp_path, capsys):
    assert main(["demo", "--lang", "ko", "--out", str(tmp_path / "o")]) == 0
    lines = capsys.readouterr().out.splitlines()
    header = next(ln for ln in lines if ln.startswith("지표"))
    rule = lines[lines.index(header) + 1]
    first = lines[lines.index(header) + 2]
    # the value column (right aligned) must end at the same display column in every row
    from speakerjoin.cli import _width

    value_end = _width(rule.split("  ")[0]) + 2 + len(rule.split("  ")[1])
    assert _width(header.split("  ")[0] + "  " + header.split("  ")[1].strip()) <= value_end + 1
    assert _width(first[: first.index("  ", 3)]) <= value_end


def test_empty_file_and_segment_fallback_notice(tmp_path, fx, capsys):
    import speakerjoin as sj

    with pytest.raises(sj.FormatError, match="is empty"):
        sj.load_transcript(_write(tmp_path / "e.json", ""))
    argv = ["merge", str(fx("stt.srt")), "--diar", str(fx("diar.rttm"))]
    assert main([*argv, "--lang", "en"]) == 0
    assert "per segment" in capsys.readouterr().err
    assert main([*argv, "--lang", "ko"]) == 0
    assert "세그먼트 단위" in capsys.readouterr().err
    assert main([*argv, "--unit", "segment", "--lang", "en"]) == 0
    assert "per segment" not in capsys.readouterr().err
    out = tmp_path / "r.json"
    assert main([*argv, "--report", str(out), "-o", str(tmp_path / "o.srt")]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["options"]["effective_unit"] == "segment"
