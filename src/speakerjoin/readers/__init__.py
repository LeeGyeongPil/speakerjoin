"""Readers turn format-specific files into the shared model."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..errors import FormatError


def read_source(src: Any) -> tuple[Any, str]:
    """Return ``(data, label)`` where data is parsed JSON, raw text, or the object itself.

    ``src`` may be a path, a text/JSON string (contains a newline or starts with ``{``/``[``),
    an already-parsed dict/list, or any other Python object (returned unchanged).
    """
    if isinstance(src, str) and ("\n" in src or src.lstrip()[:1] in ("{", "[")):
        return _decode(src, "<string>"), "<string>"
    if isinstance(src, (str, os.PathLike)):
        path = Path(src)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise FormatError("not_found", path=path, detail=exc.strerror or str(exc)) from exc
        except UnicodeDecodeError as exc:
            raise FormatError("not_utf8", path=path, reason=exc.reason) from exc
        if not text.strip():
            raise FormatError("empty", label=str(path))
        return _decode(text, str(path)), str(path)
    return src, "<object>"


def _decode(text: str, label: str) -> Any:
    if text.lstrip()[:1] in ("{", "["):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FormatError(
                "bad_json", label=label, line=exc.lineno, column=exc.colno, detail=exc.msg
            ) from exc
    return text


def num(value: Any, where: str) -> float | None:
    """Parse an optional number; None stays None, junk raises FormatError."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise FormatError("not_number", where=where, value=value)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise FormatError("not_number", where=where, value=value) from exc
