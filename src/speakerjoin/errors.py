"""Exception hierarchy. Every error raised on purpose derives from SpeakerJoinError.

Each error carries a message ``key`` plus ``params``. ``str(exc)`` is always the English text
(library users); the CLI renders the same key and params in the chosen display language.
"""

from __future__ import annotations

from collections.abc import Sequence

from .i18n import t


class SpeakerJoinError(Exception):
    """Base class for all errors raised by speakerjoin."""

    key: str = ""
    params: dict[str, object]

    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params = params
        super().__init__(t("en", f"err.{key}", **params))


class UnknownFormatError(SpeakerJoinError):
    """The input shape matches none of the supported formats."""

    def __init__(self, label: str, supported: Sequence[str], hint: str = "") -> None:
        self.label = label
        self.supported = tuple(supported)
        message = (
            f"Could not detect the format of {label}. "
            f"Supported formats: {', '.join(self.supported)}. "
            "Pass format=... (CLI: --stt-format / --diar-format) to force one."
        )
        if hint:
            message = f"{message} {hint}"
        self.key = ""
        self.params = {}
        Exception.__init__(self, message)


class FormatError(SpeakerJoinError):
    """The input has a known format but its content is invalid or unreadable."""


class ThresholdSyntaxError(SpeakerJoinError):
    """A --fail-on expression could not be parsed."""


class ConfigError(SpeakerJoinError, ValueError):
    """An option value is out of range (also a ``ValueError`` for backward compatibility)."""
