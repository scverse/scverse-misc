"""Shared logger for scverse packages.

Skeleton: one ``scverse`` parent logger owning a single handler (rich if
installed, else plain), with package loggers as children. Control via
:data:`config`; attach any :class:`logging.Filter` with :meth:`config.add_filter`.

Records stay untouched: context travels as record attributes (``time_passed``,
``deep``), and only the text formatter renders them. A JSON handler attached
next to ours sees the original message plus those attributes, never a
pre-rendered string.

- ``record.time_passed`` (a ``timedelta``) renders as an appended ``(H:MM:SS)``.
- ``record.deep`` renders as an appended ``: detail``.

scanpy's ``time=`` / ``deep=`` keywords and the ``-> datetime`` return are a
call-site concern, so they live in an **opt-in** logger::

    log = get_logger("scanpy", timed=True)
    t = log.info("normalizing")  # returns a datetime
    log.info("finished", time=t)  # -> "finished (0:00:03)"
    log.info("done", time=t, deep="42 cells dropped")
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Literal, Self, cast, overload

__all__ = ["TimedLogger", "config", "get_logger"]

_ROOT = "scverse"
HINT = (logging.INFO + logging.DEBUG) // 2  # 15; used by the timed logger
logging.addLevelName(HINT, "HINT")


class _Extras(logging.Filter):
    """Turn the optional ``time_passed``/``deep`` record attributes into render-ready fields.

    Sets ``record.elapsed`` / ``record.detail`` on *every* record (empty when absent)
    so the ``{``-style formatter never hits a missing key. The message itself is
    never modified.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        td = getattr(record, "time_passed", None)
        # None or zero -> nothing (matches scanpy); strip sub-second noise
        record.elapsed = f" ({timedelta(seconds=int(td.total_seconds()))})" if td else ""
        deep = getattr(record, "deep", None)
        record.detail = "" if deep is None else f": {deep}"
        return True


_FORMAT = "{message}{elapsed}{detail}"  # rich renders the level itself; plain prefixes it


def _make_handler(use_rich: bool) -> logging.Handler:
    if use_rich:
        if not _rich_available():
            raise ImportError("rich is not installed; install scverse-misc[rich] or leave config.rich as None/False")
        from rich.console import Console
        from rich.logging import RichHandler

        # stderr to match the plain handler (and scanpy)
        handler: logging.Handler = RichHandler(console=Console(stderr=True), show_path=False, show_time=False)
        handler.setFormatter(logging.Formatter(_FORMAT, style="{"))
        return handler
    handler = logging.StreamHandler()  # defaults to stderr
    handler.setFormatter(logging.Formatter(f"{{levelname}}: {_FORMAT}", style="{"))
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
        if not isinstance(logging.getLevelName(value.upper()), int):
            raise ValueError(f"unknown log level name: {value!r}")
        return value.upper()
    name = logging.getLevelName(value)
    if name.startswith("Level "):
        raise ValueError(f"unknown log level: {value!r}")
    return name


def _reinstall(verbosity: str | int, rich: bool | None) -> None:
    """Apply ``verbosity`` + ``rich`` to the shared ``scverse`` logger.

    Swaps the handler only when the rich state actually changed, carrying any
    registered filters across; on first call it seeds :class:`_Extras`.
    """
    root = logging.getLogger(_ROOT)
    root.propagate = False  # one handler here; don't double-log via root
    root.setLevel(_canonical_level(verbosity))
    use_rich = _rich_available() if rich is None else rich
    current = root.handlers[0] if root.handlers else None
    # a plain handler is a StreamHandler, rich's RichHandler is not -> cheap rich test
    if current is None or isinstance(current, logging.StreamHandler) == use_rich:
        filters = list(current.filters) if current else [_Extras()]  # carry filters across
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

    class _LogConfig(BaseModel, _FilterAccess):
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

    class _LogConfig(_FilterAccess):  # type: ignore[no-redef]
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


config = _LogConfig()


class TimedLogger:
    """Opt-in scanpy-style wrapper: ``time=``/``deep=`` keywords + a ``datetime`` return.

    Sets ``time_passed``/``deep`` on the record (rendered by the shared formatter)
    and returns the current time so callers can thread it.
    Everything else delegates to the underlying real logger.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401  # transparent delegation to the real logger
        if name == "_logger":
            raise AttributeError(name)
        return getattr(self._logger, name)

    def _emit(
        self,
        level: int,
        msg: object,
        *args: object,
        time: datetime | None = None,
        deep: object = None,
    ) -> datetime:
        now = datetime.now()
        if self._logger.isEnabledFor(level):
            extra: dict[str, object] = {}
            if time is not None:
                extra["time_passed"] = now - time  # thread the returned value (both naive)
            if deep is not None and self._logger.getEffectiveLevel() < level:
                extra["deep"] = deep
            # stacklevel=3: skip _emit + the level method so the call-site is the caller
            self._logger.log(level, msg, *args, extra=extra, stacklevel=3)
        return now

    def debug(self, msg: object, *a: object, time: datetime | None = None, deep: object = None) -> datetime:
        """Log at DEBUG; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.DEBUG, msg, *a, time=time, deep=deep)

    def hint(self, msg: object, *a: object, time: datetime | None = None, deep: object = None) -> datetime:
        """Log at HINT; return the current time (see :class:`TimedLogger`)."""
        return self._emit(HINT, msg, *a, time=time, deep=deep)

    def info(self, msg: object, *a: object, time: datetime | None = None, deep: object = None) -> datetime:
        """Log at INFO; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.INFO, msg, *a, time=time, deep=deep)

    def warning(self, msg: object, *a: object, time: datetime | None = None, deep: object = None) -> datetime:
        """Log at WARNING; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.WARNING, msg, *a, time=time, deep=deep)

    def error(self, msg: object, *a: object, time: datetime | None = None, deep: object = None) -> datetime:
        """Log at ERROR; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.ERROR, msg, *a, time=time, deep=deep)

    def critical(self, msg: object, *a: object, time: datetime | None = None, deep: object = None) -> datetime:
        """Log at CRITICAL; return the current time (see :class:`TimedLogger`)."""
        return self._emit(logging.CRITICAL, msg, *a, time=time, deep=deep)


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
