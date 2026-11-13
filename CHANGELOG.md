# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-14

### Added
- Readers for OpenAI `verbose_json` and `diarized_json`, faster-whisper, WhisperX, Deepgram,
  AssemblyAI, SRT and WebVTT transcripts, plus RTTM, pyannoteAI job JSON, plain JSON turns,
  `(start, end, speaker)` tuples and duck-typed pyannote `Annotation` objects.
- Format auto-detection with `--stt-format` / `--diar-format` overrides.
- Word-level speaker assignment (`overlap`, `midpoint`), segment-level fallback, `fill_nearest`,
  zero-length word handling, interpolation of untimed words.
- Word flags: `unassigned`, `filled_nearest`, `overlap`, `boundary`, `interpolated`, `zero_length`.
- SRT, WebVTT, JSON, Markdown and plain text writers with speaker-change cue splitting.
- Quality report and `--fail-on` thresholds (exit code 1 when exceeded).
- CLI (`merge`, `report`, `demo`, `formats`) in English and Korean (`--lang`, `SPEAKERJOIN_LANG`).
- Synthetic practice sample behind `speakerjoin demo`.

### Known issues

**Some Korean argparse titles and OS error messages still appear in English; planned for a later release.**

[0.1.0]: https://github.com/LeeGyeongPil/speakerjoin/releases/tag/v0.1.0
