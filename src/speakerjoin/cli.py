"""Command line interface: ``speakerjoin merge | report | demo | formats``.

Exit codes: 0 success, 1 a --fail-on threshold was exceeded, 2 bad input or usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path
from typing import NoReturn

from . import __version__
from .assign import STRATEGIES, UNITS, merge
from .detect import DIAR_FORMATS, STT_FORMATS
from .errors import ConfigError, SpeakerJoinError, ThresholdSyntaxError, UnknownFormatError
from .i18n import LANGS, resolve_lang, t
from .loaders import load_diarization, load_transcript
from .model import MergeResult, Report
from .report import check_thresholds
from .writers import to_json, to_markdown, to_srt, to_text, to_vtt

OUTPUT_FORMATS = ("srt", "vtt", "json", "md", "txt")
_EXTENSIONS = {".srt": "srt", ".vtt": "vtt", ".json": "json", ".md": "md", ".txt": "txt"}
_TABLE_METRICS = (
    "words_total", "words_untimed", "unassigned", "unassigned_ratio", "filled_nearest",
    "overlap_words", "overlap_ratio", "boundary_words", "boundary_ratio",
    "segments_multi_speaker", "segment_word_disagree", "segment_word_disagree_ratio",
    "speaker_changes", "dominant_speaker_share", "speech_without_words_sec",
)  # fmt: skip


class _CliError(SpeakerJoinError):
    """An error whose message is already localized and printed as is."""

    def __init__(self, message: str) -> None:
        self.key = ""
        self.params = {}
        Exception.__init__(self, message)


class _Parser(argparse.ArgumentParser):
    """argparse with a localized, one-line usage error and exit code 2."""

    lang = "en"

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        detail = _localize_argparse(self.lang, message)
        print(f"{t(self.lang, 'error.prefix')}: {t(self.lang, 'error.usage', detail=detail)}",
              file=sys.stderr)  # fmt: skip
        raise SystemExit(2)


# argparse builds its error text in English; map the common shapes onto our message table.
_ARGPARSE_PATTERNS = (
    (re.compile(r"^argument (.+?): invalid choice: (.+?) \(choose from (.*)\)$"),
     "argp.invalid_choice", ("arg", "value", "choices")),
    (re.compile(r"^argument (.+?): invalid (\w+) value: (.+)$"),
     "argp.invalid_value", ("arg", "kind", "value")),
    (re.compile(r"^the following arguments are required: (.+)$"), "argp.required", ("names",)),
    (re.compile(r"^argument (.+?): expected one argument$"), "argp.expected_one", ("arg",)),
    (re.compile(r"^unrecognized arguments: (.+)$"), "argp.unrecognized", ("args",)),
)  # fmt: skip


def _localize_argparse(lang: str, message: str) -> str:
    for pattern, key, names in _ARGPARSE_PATTERNS:
        match = pattern.match(message)
        if match:
            return t(lang, key, **dict(zip(names, match.groups(), strict=True)))
    return message


def _width(text: str) -> int:
    """Terminal columns: East Asian wide characters take two."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pad(text: str, width: int, right: bool = False) -> str:
    gap = " " * max(width - _width(text), 0)
    return gap + text if right else text + gap


def _add_inputs(p: argparse.ArgumentParser, lang: str) -> None:
    p.add_argument("stt", help=t(lang, "help.stt"))
    p.add_argument("--diar", required=True, metavar="FILE", help=t(lang, "help.diar"))
    p.add_argument("--stt-format", choices=STT_FORMATS, help=t(lang, "help.stt_format"))
    p.add_argument("--diar-format", choices=DIAR_FORMATS, help=t(lang, "help.diar_format"))
    p.add_argument("--file-id", help=t(lang, "help.file_id"))
    p.add_argument("--no-prefer-exclusive", action="store_true", help=t(lang, "help.no_exclusive"))
    p.add_argument(
        "--strategy", choices=STRATEGIES, default="overlap", help=t(lang, "help.strategy")
    )
    p.add_argument("--unit", choices=UNITS, default="auto", help=t(lang, "help.unit"))
    p.add_argument("--fill-nearest", action="store_true", help=t(lang, "help.fill_nearest"))
    p.add_argument("--tolerance", type=float, default=0.2, help=t(lang, "help.tolerance"))
    p.add_argument("--min-word-dur", type=float, default=0.02, help=t(lang, "help.min_word_dur"))


def _add_render(p: argparse.ArgumentParser, lang: str) -> None:
    p.add_argument("--speaker-map", action="append", default=[], metavar="OLD=NEW",
                   help=t(lang, "help.speaker_map"))  # fmt: skip
    p.add_argument("--max-chars", type=int, default=42, help=t(lang, "help.max_chars"))
    p.add_argument("--max-duration", type=float, default=7.0, help=t(lang, "help.max_duration"))


def build_parser(lang: str) -> argparse.ArgumentParser:
    parser = _Parser(prog="speakerjoin", description=t(lang, "app.description"), add_help=False)
    parser.lang = lang
    parser.add_argument("-h", "--help", action="help", help=t(lang, "help.help"))
    parser.add_argument(
        "--version",
        action="version",
        version=f"speakerjoin {__version__}",
        help=t(lang, "help.version"),
    )
    lang_help = t(lang, "help.lang")
    parser.add_argument("--lang", choices=LANGS, help=lang_help)
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)

    def command(name: str) -> argparse.ArgumentParser:
        p = sub.add_parser(
            name,
            help=t(lang, f"help.cmd.{name}"),
            description=t(lang, f"help.cmd.{name}"),
            add_help=False,
        )
        p.add_argument("-h", "--help", action="help", help=t(lang, "help.help"))
        p.lang = lang  # type: ignore[attr-defined]
        p.add_argument("--lang", choices=LANGS, default=argparse.SUPPRESS, help=lang_help)
        return p

    p = command("merge")
    _add_inputs(p, lang)
    _add_render(p, lang)
    p.add_argument("-o", "--output", metavar="FILE", help=t(lang, "help.output"))
    p.add_argument("--format", choices=OUTPUT_FORMATS, help=t(lang, "help.format"))
    p.add_argument("--report", metavar="FILE", help=t(lang, "help.report"))

    p = command("report")
    _add_inputs(p, lang)
    p.add_argument(
        "--fail-on", action="append", default=[], metavar="EXPR", help=t(lang, "help.fail_on")
    )
    p.add_argument("--json", action="store_true", help=t(lang, "help.json"))

    p = command("demo")
    p.add_argument(
        "--out", default="speakerjoin-demo", metavar="DIR", help=t(lang, "help.demo_out")
    )

    command("formats")
    return parser


# --- helpers -----------------------------------------------------------------------------


def _parse_speaker_map(values: Sequence[str], lang: str) -> dict[str, str]:
    mapping = {}
    for value in values:
        old, sep, new = value.partition("=")
        if not sep or not old.strip() or not new.strip():
            raise _CliError(t(lang, "error.speaker_map", value=value))
        mapping[old.strip()] = new.strip()
    return mapping


def _note_fallback(result: MergeResult, args: argparse.Namespace, lang: str) -> None:
    """Tell the user when 'auto' ended up assigning per segment (no word timing found)."""
    if args.unit == "auto" and result.options.get("effective_unit") == "segment":
        print(t(lang, "note.segment_fallback"), file=sys.stderr)


def _run_merge(args: argparse.Namespace) -> MergeResult:
    transcript = load_transcript(args.stt, format=args.stt_format or "auto")
    diarization = load_diarization(
        args.diar,
        format=args.diar_format or "auto",
        file_id=args.file_id,
        prefer_exclusive=not args.no_prefer_exclusive,
    )
    return merge(
        transcript,
        diarization,
        strategy=args.strategy,
        unit=args.unit,
        fill_nearest=args.fill_nearest,
        tolerance=args.tolerance,
        min_word_dur=args.min_word_dur,
    )


def _render(result: MergeResult, fmt: str, lang: str, speaker_map, max_chars, max_duration) -> str:
    kw = {"speaker_map": speaker_map, "max_chars": max_chars, "max_duration": max_duration}
    if fmt == "srt":
        return to_srt(result, **kw)
    if fmt == "vtt":
        return to_vtt(result, **kw)
    if fmt == "json":
        return to_json(result, **kw)
    if fmt == "md":
        return to_markdown(result, title=t(lang, "md.title"), **kw)
    return to_text(result, **kw)


def _report_json(result: MergeResult) -> str:
    doc = {"schema": 1, "options": result.options, "report": result.report.to_dict()}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _fmt_value(value: float) -> str:
    return str(value) if isinstance(value, int) else f"{value:.4f}".rstrip("0").rstrip(".") or "0"


def format_report(report: Report, lang: str) -> str:
    """Human-readable quality table (metric names stay English so --fail-on is language free)."""
    metrics = report.to_dict()
    rows = [(m, _fmt_value(metrics[m]), t(lang, f"metric.{m}")) for m in _TABLE_METRICS]
    head = (t(lang, "report.header.metric"), t(lang, "report.header.value"),
            t(lang, "report.header.meaning"))  # fmt: skip
    w0 = max(_width(head[0]), *(_width(r[0]) for r in rows))
    w1 = max(_width(head[1]), *(_width(r[1]) for r in rows))
    lines = [t(lang, "report.title"), ""]
    lines.append(f"{_pad(head[0], w0)}  {_pad(head[1], w1, right=True)}  {head[2]}")
    lines.append(f"{'-' * w0}  {'-' * w1}  {'-' * max(_width(head[2]), 7)}")
    lines += [f"{_pad(a, w0)}  {_pad(b, w1, right=True)}  {c}" for a, b, c in rows]
    lines += ["", t(lang, "report.speakers")]
    for speaker, seconds in report.talk_time.items():
        share = report.word_share.get(speaker, 0.0)
        lines.append(f"  {speaker}: {seconds:.1f}s, {share:.0%}")
    lines += [
        "",
        t(lang, "report.disagree", n=report.segment_word_disagree, total=report.words_total),
    ]
    return "\n".join(lines) + "\n"


def _error(lang: str, exc: Exception) -> int:
    if isinstance(exc, UnknownFormatError):
        message = t(
            lang, "error.unknown_format", label=exc.label, supported=", ".join(exc.supported)
        )
    elif isinstance(exc, _CliError):
        message = str(exc)  # already localized
    elif isinstance(exc, SpeakerJoinError):
        detail = t(lang, f"err.{exc.key}", **exc.params)
        if isinstance(exc, ThresholdSyntaxError):
            message = t(lang, "error.threshold", detail=detail)
        elif isinstance(exc, ConfigError):
            message = t(lang, "error.usage", detail=detail)
        else:
            message = t(lang, "error.input", detail=detail)
    else:
        message = t(lang, "error.usage", detail=exc)
    print(f"{t(lang, 'error.prefix')}: {message}", file=sys.stderr)
    return 2


# --- commands ----------------------------------------------------------------------------


def _cmd_merge(args: argparse.Namespace, lang: str) -> int:
    speaker_map = _parse_speaker_map(args.speaker_map, lang)
    fmt = args.format
    if fmt is None and args.output:
        fmt = _EXTENSIONS.get(Path(args.output).suffix.lower())
        if fmt is None:
            raise _CliError(t(lang, "error.unknown_output", name=Path(args.output).name))
    fmt = fmt or "srt"
    result = _run_merge(args)
    text = _render(result, fmt, lang, speaker_map, args.max_chars, args.max_duration)
    try:
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        if args.report:
            Path(args.report).write_text(_report_json(result), encoding="utf-8")
    except OSError as exc:
        raise _CliError(
            t(lang, "error.write", path=args.output or args.report, detail=exc.strerror or exc)
        ) from exc
    r = result.report
    print(t(lang, "summary.merge", words=r.words_total, utterances=len(result.utterances),
            unassigned=r.unassigned), file=sys.stderr)  # fmt: skip
    _note_fallback(result, args, lang)
    return 0


def _cmd_report(args: argparse.Namespace, lang: str) -> int:
    for expr in args.fail_on:  # validate before doing any work
        check_thresholds(_EMPTY_REPORT, [expr])
    result = _run_merge(args)
    if args.json:
        sys.stdout.write(_report_json(result))
    else:
        sys.stdout.write(format_report(result.report, lang))
    _note_fallback(result, args, lang)
    failed = check_thresholds(result.report, args.fail_on)
    for detail in failed:
        print(t(lang, "threshold.failed", detail=detail))
    return 1 if failed else 0


def _cmd_demo(args: argparse.Namespace, lang: str) -> int:
    base = files("speakerjoin").joinpath("samples")
    transcript = load_transcript(base.joinpath("meeting.whisper.json").read_text(encoding="utf-8"))
    diarization = load_diarization(base.joinpath("meeting.rttm").read_text(encoding="utf-8"))
    result = merge(transcript, diarization)
    out = Path(args.out)
    print(t(lang, "demo.synthetic"))
    print()
    sys.stdout.write(format_report(result.report, lang))
    try:
        out.mkdir(parents=True, exist_ok=True)
        print()
        for name, fmt in (("demo.srt", "srt"), ("demo.vtt", "vtt"), ("demo.json", "json"),
                          ("demo.md", "md")):  # fmt: skip
            path = out / name
            path.write_text(_render(result, fmt, lang, None, 42, 7.0), encoding="utf-8")
            print(t(lang, "demo.wrote", path=path))
    except OSError as exc:
        raise _CliError(t(lang, "error.write", path=out, detail=exc.strerror or exc)) from exc
    return 0


def _cmd_formats(_args: argparse.Namespace, lang: str) -> int:
    print(t(lang, "formats.title"))
    print(f"  {t(lang, 'formats.stt')}: {', '.join(STT_FORMATS)}")
    print(f"  {t(lang, 'formats.diar')}: {', '.join(DIAR_FORMATS)}")
    print(f"  {t(lang, 'formats.out')}: {', '.join(OUTPUT_FORMATS)}")
    return 0


def _empty_report() -> Report:
    return Report(0, 0, 0, 0.0, 0, 0, 0.0, 0, 0.0, 0, 0, 0.0, 0, 0.0, 0.0)


_EMPTY_REPORT = _empty_report()
_COMMANDS = {"merge": _cmd_merge, "report": _cmd_report, "demo": _cmd_demo, "formats": _cmd_formats}


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    lang = resolve_lang(argv, os.environ)
    parser = build_parser(lang)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    if args.command is None:
        parser.print_help()
        return 2
    try:
        return _COMMANDS[args.command](args, lang)
    except (SpeakerJoinError, ValueError) as exc:
        return _error(lang, exc)
    except BrokenPipeError:  # e.g. `speakerjoin merge ... | head`
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
