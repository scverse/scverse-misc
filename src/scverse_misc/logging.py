"""Shared logging for scverse packages.

Each package gets a child of the ``scverse`` logger via :func:`get_logger`,
so users control all scverse packages’ output in one place with :data:`config`
(verbosity, rich output, filters).

:func:`get_logger` with ``timed=True`` returns a :class:`TimedLogger`,
which supports scanpy-style ``time=`` and ``deep=`` arguments
(``deep`` is only shown if verbosity is higher than the message’s level)::

    log = get_logger("scanpy", timed=True)
    t = log.info("normalizing")  # returns the current time
    log.info("finished", time=t)  # -> "finished (0:00:03)"
    log.info("done", deep="42 cells dropped")  # -> "done: 42 cells dropped"

The elapsed time and details are stored as ``time_passed`` and ``deep`` attributes on the log record,
so custom handlers (e.g. for structured logging) receive them unformatted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal, Self, TypedDict, Unpack, cast, overload, override

if TYPE_CHECKING:
    from collections.abc import Mapping
    from logging import _ExcInfoType

__all__ = ["LogConfig", "TimedLogger", "config", "get_logger"]

_ROOT = "scverse"
HINT = (logging.INFO + logging.DEBUG) // 2  # 15; used by the timed logger
logging.addLevelName(HINT, "HINT")


class _Formatter(logging.Formatter):
    """``{``-style formatter that renders ``{extra}`` from optional record attributes.

    Each entry in ``extra`` maps a record attribute to a fragment that is appended
    only if the record carries that attribute (and it isn't ``None``).
    Formatting happens here only, so records keep their raw values.
    """

    def __init__(self, fmt: str, extra: Mapping[str, str]) -> None:
        super().__init__(fmt, style="{")
        self.extra = extra

    @override
    def formatMessage(self, record: logging.LogRecord) -> str:
        values = vars(record)
        extra = "".join(frag.format_map(values) for attr, frag in self.extra.items() if values.get(attr) is not None)
        return self._fmt.format_map({**values, "extra": extra})  # type: ignore[union-attr]


_FORMAT = "{message}{extra}"  # rich renders the level itself; plain prefixes it
_FORMAT_EXTRA = dict(time_passed=" ({time_passed})", deep=": {deep}")


def _make_handler(use_rich: bool) -> logging.Handler:
    if use_rich:
        if not _rich_available():
            msg = "rich is not installed; install scverse-misc[rich] or leave config.rich as None/False"
            raise ImportError(msg)
        from rich.console import Console
        from rich.logging import RichHandler

        # stderr to match the plain handler (and scanpy)
        handler: logging.Handler = RichHandler(console=Console(stderr=True), show_path=False, show_time=False)
        handler.setFormatter(_Formatter(_FORMAT, _FORMAT_EXTRA))
        return handler
    handler = logging.StreamHandler()  # defaults to stderr
    handler.setFormatter(_Formatter(f"{{levelname}}: {_FORMAT}", _FORMAT_EXTRA))
    return handler


def _rich_available() -> bool:
    from importlib.util import find_spec

    return find_spec("rich") is not None


# The shared ``scverse`` logger is the single source of truth for live state;
# both config tiers drive it through the helpers below. The full tier adds
# pydantic validate-on-assignment for verbosity/rich (install scverse-misc[logging]);
# without pydantic the reduced tier keeps the same behavior via plain properties.
try:
    from pydantic import BaseModel, ConfigDict, field_validator, model_validator

    _HAVE_PYDANTIC = True
except ImportError:
    _HAVE_PYDANTIC = False


def _canonical_level(value: str | int) -> str:
    """Validate and normalize a level to a canonical name (e.g. ``"WARNING"``)."""
    if isinstance(value, str):
        if value.upper() not in logging.getLevelNamesMapping():
            msg = f"unknown log level name: {value!r}"
            raise ValueError(msg)
        return value.upper()
    name = logging.getLevelName(value)
    if name.startswith("Level "):
        msg = f"unknown log level: {value!r}"
        raise ValueError(msg)
    return name


def _reinstall(verbosity: str | int, rich: bool | None) -> None:
    """Apply ``verbosity`` + ``rich`` to the shared ``scverse`` logger.

    Swaps the handler only when the rich state actually changed, carrying any
    registered filters across.
    """
    root = logging.getLogger(_ROOT)
    root.propagate = False  # one handler here; don't double-log via root
    root.setLevel(_canonical_level(verbosity))
    use_rich = _rich_available() if rich is None else rich
    current = root.handlers[0] if root.handlers else None
    # a plain handler is a StreamHandler, rich's RichHandler is not -> cheap rich test
    if current is None or isinstance(current, logging.StreamHandler) == use_rich:
        filters = list(current.filters) if current else []  # carry filters across
        for h in list(root.handlers):
            root.removeHandler(h)
        handler = _make_handler(use_rich)
        for f in filters:
            handler.addFilter(f)
        root.addHandler(handler)


class _FilterAccess:
    """Filter/handler accessors shared by both config tiers (all target the shared logger)."""

    @property
    def _root(self) -> logging.Logger:
        return logging.getLogger(_ROOT)

    @property
    def _filters(self) -> list[logging.Filter]:
        return cast("list[logging.Filter]", self._root.handlers[0].filters)

    def add_filter(self, filter: logging.Filter) -> None:
        """Attach a :class:`logging.Filter` to the shared handler (survives rich toggles)."""
        for h in self._root.handlers:
            h.addFilter(filter)

    def remove_filter(self, filter: logging.Filter) -> None:
        """Detach a filter added with :meth:`add_filter`."""
        for h in self._root.handlers:
            h.removeFilter(filter)


if _HAVE_PYDANTIC:

    class LogConfig(BaseModel, _FilterAccess):
        """Central logging configuration; the singleton instance is :data:`config`.

        A pydantic model, so ``verbosity``/``rich`` are validated on assignment.
        Available when ``scverse-misc[logging]`` (i.e. ``pydantic``) is installed;
        without it the reduced tier keeps the same verbosity/rich/filters behavior
        via plain properties.
        """

        model_config = ConfigDict(validate_assignment=True, validate_default=True)

        verbosity: str | int = "warning"
        """Central level for all scverse loggers; a level name (``"info"``) or an int."""

        rich: bool | None = None
        """Force rich rendering on/off; ``None`` auto-detects whether rich is installed."""

        @field_validator("verbosity")
        @classmethod
        def _validate_level(cls, value: str | int) -> str:
            """Validate and normalize the level (delegates to the shared helper)."""
            return _canonical_level(value)

        @model_validator(mode="after")
        def _apply(self) -> Self:
            """Re-apply the current settings onto the shared ``scverse`` logger."""
            _reinstall(self.verbosity, self.rich)
            return self

else:

    class LogConfig(_FilterAccess):  # type: ignore[no-redef]
        """Central logging configuration; the singleton instance is :data:`config`.

        Reduced tier, used when ``pydantic`` is absent. Logging works fully
        (verbosity, rich toggle, filters); install ``scverse-misc[logging]`` to
        get pydantic-based validate-on-assignment for the config fields.
        """

        def __init__(self) -> None:
            self._rich: bool | None = None  # None = auto-detect rich
            _reinstall("warning", self._rich)

        @property
        def verbosity(self) -> str | int:
            """Central level for all scverse loggers. Set with a name (``"info"``) or int."""
            return logging.getLevelName(logging.getLogger(_ROOT).level)

        @verbosity.setter
        def verbosity(self, level: str | int) -> None:
            _reinstall(level, self._rich)

        @property
        def rich(self) -> bool | None:
            """Force rich on/off; ``None`` auto-detects. Set ``True``/``False``/``None``."""
            return self._rich

        @rich.setter
        def rich(self, enabled: bool | None) -> None:
            self._rich = None if enabled is None else bool(enabled)  # match the pydantic tier's coercion
            _reinstall(self.verbosity, self._rich)


config = LogConfig()
"""Singleton logging configuration for all scverse loggers."""


class _LogKwargs(TypedDict, total=False):
    exc_info: _ExcInfoType
    stack_info: bool
    stacklevel: int
    extra: Mapping[str, object] | None


class TimedLogger(logging.LoggerAdapter[logging.Logger]):
    """Opt-in scanpy-style adapter: ``time=``/``deep=`` keywords + a ``datetime`` return.

    Sets ``time_passed``/``deep`` on the record (rendered by the shared formatter)
    and returns the current time so callers can thread it.
    """

    def _emit(
        self,
        level: int,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
        **kwargs: Unpack[_LogKwargs],
    ) -> datetime:
        now = datetime.now()
        if self.logger.isEnabledFor(level):
            extra = dict(kwargs.get("extra") or {})
            if time is not None:
                # thread the returned value (both naive); strip sub-second noise
                extra["time_passed"] = timedelta(seconds=int((now - time).total_seconds()))
            if deep is not None and self.logger.getEffectiveLevel() < level:
                extra["deep"] = deep
            kwargs["extra"] = extra
            # +2: skip _emit + the level method so the call-site is the caller
            kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 2
            self.logger.log(level, msg, *args, **kwargs)
        return now

    def debug(  # type: ignore[override]  # returns a datetime instead of None
        self,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
        **kwargs: Unpack[_LogKwargs],
    ) -> datetime:
        """Log at DEBUG; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.DEBUG, msg, *args, time=time, deep=deep, **kwargs)

    def hint(
        self,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
        **kwargs: Unpack[_LogKwargs],
    ) -> datetime:
        """Log at HINT; return the current time (see :class:`TimedLogger`)."""
        return self._emit(HINT, msg, *args, time=time, deep=deep, **kwargs)

    def info(  # type: ignore[override]  # returns a datetime instead of None
        self,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
        **kwargs: Unpack[_LogKwargs],
    ) -> datetime:
        """Log at INFO; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.INFO, msg, *args, time=time, deep=deep, **kwargs)

    def warning(  # type: ignore[override]  # returns a datetime instead of None
        self,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
        **kwargs: Unpack[_LogKwargs],
    ) -> datetime:
        """Log at WARNING; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.WARNING, msg, *args, time=time, deep=deep, **kwargs)

    def error(  # type: ignore[override]  # returns a datetime instead of None
        self,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
        **kwargs: Unpack[_LogKwargs],
    ) -> datetime:
        """Log at ERROR; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.ERROR, msg, *args, time=time, deep=deep, **kwargs)

    def critical(  # type: ignore[override]  # returns a datetime instead of None
        self,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
        **kwargs: Unpack[_LogKwargs],
    ) -> datetime:
        """Log at CRITICAL; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.CRITICAL, msg, *args, time=time, deep=deep, **kwargs)


@overload
def get_logger(name: str, *, timed: Literal[False] = False) -> logging.Logger: ...
@overload
def get_logger(name: str, *, timed: Literal[True]) -> TimedLogger: ...
def get_logger(name: str, *, timed: bool = False) -> logging.Logger | TimedLogger:
    """Return the ``scverse.<name>`` logger a package should use.

    ``timed=False`` (default) returns a plain :class:`logging.Logger`.
    ``timed=True`` returns a :class:`TimedLogger` with scanpy-style ``time=`` /
    ``deep=`` keywords and a ``datetime`` return.
    """
    logger = logging.getLogger(name if name.startswith(f"{_ROOT}.") else f"{_ROOT}.{name}")
    return TimedLogger(logger) if timed else logger
