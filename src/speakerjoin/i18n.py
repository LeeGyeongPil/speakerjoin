"""CLI display messages in English and Korean, and the language choice rules.

Precedence: ``--lang`` > ``SPEAKERJOIN_LANG`` > ``LC_ALL`` > ``LC_MESSAGES`` > ``LANG``.
A value starting with ``ko`` selects Korean; anything else selects English.
JSON report keys are never translated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

LANGS = ("en", "ko")
ENV_VAR = "SPEAKERJOIN_LANG"

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "app.description": "Join speech-to-text output with speaker diarization into "
        "speaker-labelled transcripts and a numeric quality report.",
        "help.help": "Show this help and exit.",
        "help.version": "Show the version and exit.",
        "help.lang": "Display language: en or ko (default: SPEAKERJOIN_LANG, then the locale).",
        "help.cmd.merge": "Merge a transcript with diarization; write subtitles or a transcript.",
        "help.cmd.report": "Print the alignment quality report; optionally fail on thresholds.",
        "help.cmd.demo": "Run the built-in synthetic sample and write example outputs.",
        "help.cmd.formats": "List the supported input and output formats.",
        "help.stt": "Speech-to-text result (JSON, SRT or VTT).",
        "help.diar": "Diarization result (RTTM, pyannoteAI JSON or a JSON list of turns).",
        "help.stt_format": "Force the transcript format instead of auto-detecting it.",
        "help.diar_format": "Force the diarization format instead of auto-detecting it.",
        "help.file_id": "File ID to read when an RTTM file contains several recordings.",
        "help.no_exclusive": "Ignore exclusiveDiarization in pyannoteAI results.",
        "help.strategy": "How to choose a speaker: overlap (largest summed overlap) or midpoint.",
        "help.unit": "Assign per word, per segment, or auto (word when timing exists).",
        "help.fill_nearest": "Give unmatched words the nearest speaker.",
        "help.tolerance": "Seconds around a turn edge that make a word 'boundary' (default 0.2).",
        "help.min_word_dur": "Minimum word width in seconds for zero-length words (default 0.02).",
        "help.output": "Output file (default: print to stdout).",
        "help.format": "Output format; inferred from the output file extension when omitted.",
        "help.report": "Also write the quality report as JSON to this file.",
        "help.speaker_map": "Rename a speaker, for example SPEAKER_00=Alice (repeatable).",
        "help.max_chars": "Maximum characters per subtitle cue (default 42).",
        "help.max_duration": "Maximum seconds per subtitle cue (default 7).",
        "help.fail_on": 'Exit 1 if true, e.g. "unassigned_ratio>0.05" (repeatable).',
        "help.json": "Print the report as JSON instead of a table.",
        "help.demo_out": "Folder for the demo files (default: ./speakerjoin-demo).",
        "md.title": "Transcript",
        "demo.synthetic": "NOTE: synthetic practice sample, not a real recording.",
        "demo.wrote": "Wrote {path}",
        "report.title": "Alignment quality",
        "report.header.metric": "metric",
        "report.header.value": "value",
        "report.header.meaning": "meaning",
        "report.speakers": "Speakers (talk time, share of assigned words):",
        "report.disagree": "Assigned per segment instead of per word, {n} of {total} words "
        "would get a different speaker.",
        "metric.words_total": "words (or cues) aligned",
        "metric.words_untimed": "words without timing (interpolated)",
        "metric.unassigned": "words with no speaker",
        "metric.unassigned_ratio": "share of words with no speaker",
        "metric.filled_nearest": "words given the nearest speaker",
        "metric.overlap_words": "words spoken while 2+ speakers were active",
        "metric.overlap_ratio": "share of overlapped words",
        "metric.boundary_words": "words next to a speaker-turn edge",
        "metric.boundary_ratio": "share of boundary words",
        "metric.segments_multi_speaker": "segments containing 2+ speakers",
        "metric.segment_word_disagree": "words a per-segment assignment would label differently",
        "metric.segment_word_disagree_ratio": "share of such words",
        "metric.speaker_changes": "speaker changes in the transcript",
        "metric.dominant_speaker_share": "word share of the busiest speaker",
        "metric.speech_without_words_sec": "seconds of speech turns with no words",
        "formats.title": "Supported formats",
        "formats.stt": "Transcript input",
        "formats.diar": "Diarization input",
        "formats.out": "Output",
        "summary.merge": "{words} words, {utterances} utterances, unassigned {unassigned}.",
        "threshold.failed": "Threshold exceeded: {detail}",
        "error.prefix": "error",
        "error.unknown_format": "Cannot detect the format of {label}. Supported: {supported}. "
        "Use --stt-format or --diar-format to force one.",
        "error.input": "Invalid input: {detail}",
        "error.threshold": "Invalid --fail-on: {detail}",
        "error.usage": "Invalid usage: {detail}",
        "error.speaker_map": "Invalid --speaker-map {value!r}: use OLD=NEW, e.g. SPEAKER_00=Alice.",
        "error.unknown_output": "Cannot infer the output format from {name!r}. Use --format "
        "srt|vtt|json|md|txt.",
        "error.write": "Cannot write {path}: {detail}",
        "note.segment_fallback": "Note: no word timing found, so speakers were assigned per "
        "segment. Request word timestamps from your speech-to-text tool for word-level results.",
        "argp.invalid_choice": "argument {arg}: invalid choice {value} (choose from {choices})",
        "argp.invalid_value": "argument {arg}: invalid {kind} value {value}",
        "argp.required": "the following arguments are required: {names}",
        "argp.expected_one": "argument {arg}: expected one argument",
        "argp.unrecognized": "unrecognized arguments: {args}",
        "err.not_found": "Cannot read {path}: {detail}. Check that the path exists.",
        "err.not_utf8": "{path} is not valid UTF-8 text: {reason}. Save the file as UTF-8.",
        "err.empty": "{label} is empty. Check that the file was written completely.",
        "err.bad_json": "{label}: invalid JSON at line {line}, column {column}: {detail}.",
        "err.not_number": "{where}: expected a number, got {value!r}.",
        "err.wrong_role_diar": "{label} looks like a diarization file ({name}), not a transcript. "
        "Pass it as the diarization input instead.",
        "err.wrong_role_stt": "{label} looks like a transcript ({name}), not a diarization "
        "result. Pass it as the transcript input instead.",
        "err.must_be_text": "{label}: {name} input must be text, got {got}.",
        "err.must_be_object": "{label}: {name} input must be a JSON object.",
        "err.start_end_required": "{where}: start and end are required.",
        "err.end_before_start": "{where}: end ({end}) is before start ({start}).",
        "err.speaker_missing": "{where}: speaker label is missing.",
        "err.rttm_fields": "{where}: an RTTM SPEAKER line needs at least 8 fields, got {count}.",
        "err.rttm_numbers": "{where}: start and duration must be numbers, "
        "got {start!r} and {dur!r}.",
        "err.rttm_negative_duration": "{where}: duration must not be negative, got {dur}.",
        "err.rttm_several_ids": "{label} contains several file IDs ({ids}). "
        "Pass file_id=... (CLI: --file-id) to choose one.",
        "err.rttm_no_file_id": "{label} has no turns for file ID {file_id!r}. "
        "Available: {available}.",
        "err.pyannoteai_no_list": "pyannoteAI result has no 'diarization' list. Pass the "
        "finished job (status 'succeeded') including its 'output' object.",
        "err.json_shape": "Diarization JSON must be a list of {shape} objects.",
        "err.turn_object": "{where}: expected an object with start, end, speaker.",
        "err.turn_tuple": "{where}: expected a (start, end, speaker) tuple.",
        "err.expected_list": "{where}: expected a list, got {got}.",
        "err.expected_object": "{where}: expected an object, got {got}.",
        "err.segment_no_bounds": "A segment has no start/end and no timed words to derive "
        "them from. Check that the file really is the declared format.",
        "err.segment_needs_numbers": "segments[{index}] needs numeric start and end.",
        "err.deepgram_shape": "Deepgram JSON needs results.channels[0].alternatives[0]. "
        "Pass the full response body, not just the words list.",
        "err.sub_no_timing": "{fmt} block {number} has no 'start --> end' timing line: {line!r}.",
        "err.sub_bad_timing": "{fmt} block {number}: cannot parse timing line {line!r}. "
        "Expected HH:MM:SS,mmm --> HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT).",
        "err.threshold_syntax": "Cannot parse threshold {expr!r}. Use METRIC<OP>NUMBER with OP "
        'one of > >= < <=, for example "unassigned_ratio>0.05".',
        "err.threshold_metric": "Unknown metric {name!r} in {expr!r}. Available: {available}.",
        "err.opt_strategy": "strategy must be one of {allowed}, got {got!r}",
        "err.opt_unit": "unit must be one of {allowed}, got {got!r}",
        "err.opt_min_word_dur": "min_word_dur must be greater than 0 seconds",
        "err.opt_tolerance": "tolerance must not be negative",
    },
    "ko": {
        "app.description": "받아쓰기(STT) 결과와 화자 분리 결과를 합쳐 화자별 대본·자막과 "
        "정렬 품질 수치를 만듭니다.",
        "help.help": "도움말을 보여 주고 끝냅니다.",
        "help.version": "버전을 보여 주고 끝냅니다.",
        "help.lang": "표시 언어: en 또는 ko (기본값: SPEAKERJOIN_LANG, 그다음 로캘).",
        "help.cmd.merge": "받아쓰기와 화자 분리를 합쳐 자막이나 대본을 씁니다.",
        "help.cmd.report": "정렬 품질 보고를 출력합니다. 임계값을 넘으면 실패시킬 수 있습니다.",
        "help.cmd.demo": "내장 합성 샘플로 합치기를 돌리고 예시 파일을 씁니다.",
        "help.cmd.formats": "지원하는 입력·출력 형식을 보여 줍니다.",
        "help.stt": "받아쓰기 결과(JSON, SRT, VTT).",
        "help.diar": "화자 분리 결과(RTTM, pyannoteAI JSON, 구간 목록 JSON).",
        "help.stt_format": "자동 감지 대신 받아쓰기 형식을 지정합니다.",
        "help.diar_format": "자동 감지 대신 화자 분리 형식을 지정합니다.",
        "help.file_id": "RTTM 에 녹음이 여러 개일 때 읽을 파일 ID.",
        "help.no_exclusive": "pyannoteAI 결과의 exclusiveDiarization 을 쓰지 않습니다.",
        "help.strategy": "화자 고르는 방법: overlap(겹친 시간 합 최대) 또는 midpoint(중점).",
        "help.unit": "단어별, 세그먼트별, auto(시각이 있으면 단어별)로 배정합니다.",
        "help.fill_nearest": "배정되지 않은 단어에 가장 가까운 화자를 붙입니다.",
        "help.tolerance": "화자 구간 경계 앞뒤 몇 초 안의 단어를 '경계'로 볼지(기본 0.2).",
        "help.min_word_dur": "길이 0 단어에 줄 최소 폭(초, 기본 0.02).",
        "help.output": "출력 파일(기본: 표준 출력).",
        "help.format": "출력 형식. 생략하면 출력 파일 확장자로 정합니다.",
        "help.report": "품질 보고를 JSON 으로 이 파일에도 씁니다.",
        "help.speaker_map": "화자 이름 바꾸기, 예: SPEAKER_00=Alice (여러 번 가능).",
        "help.max_chars": "자막 한 줄 최대 글자 수(기본 42).",
        "help.max_duration": "자막 한 줄 최대 길이(초, 기본 7).",
        "help.fail_on": '식이 참이면 종료 코드 1, 예: "unassigned_ratio>0.05" (여러 번 가능).',
        "help.json": "보고서를 표 대신 JSON 으로 출력합니다.",
        "help.demo_out": "데모 파일을 쓸 폴더(기본: ./speakerjoin-demo).",
        "md.title": "대본",
        "demo.synthetic": "안내: 연습용 합성 샘플이며 실제 녹음이 아닙니다.",
        "demo.wrote": "씀: {path}",
        "report.title": "정렬 품질",
        "report.header.metric": "지표",
        "report.header.value": "값",
        "report.header.meaning": "뜻",
        "report.speakers": "화자별(발화 시간, 배정된 단어 비중):",
        "report.disagree": "단어별이 아니라 세그먼트별로 배정했다면 {total}개 중 {n}개 단어에 "
        "다른 화자가 붙었을 것입니다.",
        "metric.words_total": "정렬한 단어(또는 자막 줄) 수",
        "metric.words_untimed": "시각이 없어 보간한 단어 수",
        "metric.unassigned": "화자가 없는 단어 수",
        "metric.unassigned_ratio": "화자가 없는 단어 비율",
        "metric.filled_nearest": "가장 가까운 화자를 붙인 단어 수",
        "metric.overlap_words": "2명 이상 동시 발화 중인 단어 수",
        "metric.overlap_ratio": "겹침 단어 비율",
        "metric.boundary_words": "화자 구간 경계 근처 단어 수",
        "metric.boundary_ratio": "경계 단어 비율",
        "metric.segments_multi_speaker": "2명 이상이 걸친 세그먼트 수",
        "metric.segment_word_disagree": "세그먼트 단위 배정이면 다르게 붙었을 단어 수",
        "metric.segment_word_disagree_ratio": "그런 단어의 비율",
        "metric.speaker_changes": "대본 안의 화자 전환 횟수",
        "metric.dominant_speaker_share": "가장 많이 말한 화자의 단어 비중",
        "metric.speech_without_words_sec": "단어가 없는 발화 구간 합(초)",
        "formats.title": "지원 형식",
        "formats.stt": "받아쓰기 입력",
        "formats.diar": "화자 분리 입력",
        "formats.out": "출력",
        "summary.merge": "단어 {words}개, 발화 {utterances}개, 미배정 {unassigned}개.",
        "threshold.failed": "임계값 초과: {detail}",
        "error.prefix": "오류",
        "error.unknown_format": "{label} 의 형식을 알 수 없습니다. 지원 형식: {supported}. "
        "--stt-format 또는 --diar-format 으로 직접 지정하세요.",
        "error.input": "입력이 올바르지 않습니다: {detail}",
        "error.threshold": "--fail-on 식이 올바르지 않습니다: {detail}",
        "error.usage": "사용법이 올바르지 않습니다: {detail}",
        "error.speaker_map": "--speaker-map {value!r} 이(가) 올바르지 않습니다. "
        "OLD=NEW 형식으로 쓰세요. 예: SPEAKER_00=Alice.",
        "error.unknown_output": "{name!r} 에서 출력 형식을 알 수 없습니다. "
        "--format srt|vtt|json|md|txt 로 지정하세요.",
        "error.write": "{path} 에 쓸 수 없습니다: {detail}",
        "note.segment_fallback": "안내: 단어 시각을 찾지 못해 세그먼트 단위로 화자를 배정했습니다. "
        "단어 단위 결과가 필요하면 받아쓰기 도구에서 단어 타임스탬프를 요청하세요.",
        "argp.invalid_choice": "인자 {arg}: 허용되지 않는 값 {value} (선택 가능: {choices})",
        "argp.invalid_value": "인자 {arg}: {kind} 값이 올바르지 않습니다 {value}",
        "argp.required": "필수 인자가 빠졌습니다: {names}",
        "argp.expected_one": "인자 {arg}: 값이 하나 필요합니다",
        "argp.unrecognized": "알 수 없는 인자: {args}",
        "err.not_found": "{path} 을(를) 읽을 수 없습니다: {detail}. 경로가 맞는지 확인하세요.",
        "err.not_utf8": "{path} 은(는) 올바른 UTF-8 텍스트가 아닙니다: {reason}. "
        "파일을 UTF-8 로 저장하세요.",
        "err.empty": "{label} 이(가) 비어 있습니다. 파일이 끝까지 쓰였는지 확인하세요.",
        "err.bad_json": "{label}: JSON 이 올바르지 않습니다 ({line}행 {column}열): {detail}.",
        "err.not_number": "{where}: 숫자여야 하는데 {value!r} 이(가) 들어 있습니다.",
        "err.wrong_role_diar": "{label} 은(는) 받아쓰기가 아니라 화자 분리 파일({name})로 "
        "보입니다. 화자 분리 입력(--diar)으로 넘기세요.",
        "err.wrong_role_stt": "{label} 은(는) 화자 분리 결과가 아니라 받아쓰기({name})로 "
        "보입니다. 받아쓰기 입력으로 넘기세요.",
        "err.must_be_text": "{label}: {name} 입력은 텍스트여야 하는데 {got} 이(가) 들어 있습니다.",
        "err.must_be_object": "{label}: {name} 입력은 JSON 객체여야 합니다.",
        "err.start_end_required": "{where}: start 와 end 가 필요합니다.",
        "err.end_before_start": "{where}: end({end})가 start({start})보다 앞입니다.",
        "err.speaker_missing": "{where}: 화자 이름이 없습니다.",
        "err.rttm_fields": "{where}: RTTM SPEAKER 줄에는 필드가 8개 이상 필요한데 "
        "{count}개뿐입니다.",
        "err.rttm_numbers": "{where}: 시작과 길이는 숫자여야 하는데 {start!r}, {dur!r} 이(가) "
        "들어 있습니다.",
        "err.rttm_negative_duration": "{where}: 길이는 음수일 수 없습니다 ({dur}).",
        "err.rttm_several_ids": "{label} 에 파일 ID 가 여러 개 있습니다 ({ids}). "
        "file_id=... (CLI: --file-id)로 하나를 고르세요.",
        "err.rttm_no_file_id": "{label} 에 파일 ID {file_id!r} 의 구간이 없습니다. "
        "있는 ID: {available}.",
        "err.pyannoteai_no_list": "pyannoteAI 결과에 'diarization' 목록이 없습니다. "
        "'output' 객체가 들어 있는 완료된 작업(status 'succeeded')을 넘기세요.",
        "err.json_shape": "화자 분리 JSON 은 {shape} 객체의 목록이어야 합니다.",
        "err.turn_object": "{where}: start, end, speaker 를 가진 객체여야 합니다.",
        "err.turn_tuple": "{where}: (start, end, speaker) 튜플이어야 합니다.",
        "err.expected_list": "{where}: 목록이어야 하는데 {got} 이(가) 들어 있습니다.",
        "err.expected_object": "{where}: 객체여야 하는데 {got} 이(가) 들어 있습니다.",
        "err.segment_no_bounds": "세그먼트에 start/end 가 없고 시각이 있는 단어도 없어 "
        "구간을 정할 수 없습니다. 파일이 지정한 형식이 맞는지 확인하세요.",
        "err.segment_needs_numbers": "segments[{index}] 에는 숫자 start 와 end 가 필요합니다.",
        "err.deepgram_shape": "Deepgram JSON 에는 results.channels[0].alternatives[0] "
        "가 필요합니다. 단어 목록만이 아니라 응답 본문 전체를 넘기세요.",
        "err.sub_no_timing": "{fmt} {number}번째 블록에 'start --> end' 시간 줄이 "
        "없습니다: {line!r}.",
        "err.sub_bad_timing": "{fmt} {number}번째 블록: 시간 줄 {line!r} 을(를) 읽을 수 없습니다. "
        "HH:MM:SS,mmm --> HH:MM:SS,mmm (SRT) 또는 HH:MM:SS.mmm (VTT) 형식이어야 합니다.",
        "err.threshold_syntax": "임계값 {expr!r} 을(를) 읽을 수 없습니다. "
        "지표<연산자>숫자 형식으로 쓰고 "
        '연산자는 > >= < <= 중 하나입니다. 예: "unassigned_ratio>0.05".',
        "err.threshold_metric": "{expr!r} 의 지표 {name!r} 을(를) 알 수 없습니다. "
        "사용 가능: {available}.",
        "err.opt_strategy": "strategy 는 {allowed} 중 하나여야 합니다 (입력: {got!r})",
        "err.opt_unit": "unit 은 {allowed} 중 하나여야 합니다 (입력: {got!r})",
        "err.opt_min_word_dur": "min_word_dur 는 0초보다 커야 합니다",
        "err.opt_tolerance": "tolerance 는 음수일 수 없습니다",
    },
}


def _pick(value: str | None) -> str | None:
    if not value:
        return None
    return "ko" if value.lower().startswith("ko") else "en"


def resolve_lang(argv: Sequence[str], env: Mapping[str, str]) -> str:
    """Decide the display language. ``argv`` is scanned for ``--lang X`` / ``--lang=X``."""
    for i, arg in enumerate(argv):
        value = None
        if arg == "--lang" and i + 1 < len(argv):
            value = argv[i + 1]
        elif arg.startswith("--lang="):
            value = arg.split("=", 1)[1]
        if value in LANGS:
            return value
    picked = _pick(env.get(ENV_VAR))
    if picked:
        return picked
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        picked = _pick(env.get(name))
        if picked:
            return picked
    return "en"


def t(lang: str, key: str, **fields: object) -> str:
    """Look up a message and fill its placeholders."""
    text = MESSAGES[lang][key]
    return text.format(**fields) if fields else text
