"""Shared logger for scverse packages.

Skeleton: one ``scverse`` parent logger owning a single handler (rich if
installed, else plain), with package loggers as children. Control via
:data:`config`. The only extension point is :class:`Rule` — subclass it to
filter or rewrite output; register any number with :meth:`config.add_rule`.

Two **universal rules** ship enabled by default and are no-ops until a record
carries the matching attribute:

- :class:`Elapsed` renders ``record.time_passed`` (a ``timedelta``): substitutes
  ``{time_passed}`` in the message, else appends ``(H:MM:SS)``.
- :class:`Deep` appends ``record.deep`` as ``": detail"``.

Because rules run on the handler, they render identically under rich and plain.

scanpy's ``time=`` / ``deep=`` keywords and the ``-> datetime`` return are a
call-site concern a rule cannot provide (a rule runs after the call returns),
so they live in an **opt-in** logger: ``get_logger("scanpy", timed=True)``::

    log = get_logger("scanpy", timed=True)
    t = log.info("normalizing")  # returns a datetime
    log.info("finished ({time_passed})", time=t)  # Elapsed rule renders it
    log.info("done", time=t, deep="42 cells dropped")
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Literal, overload

__all__ = ["Rule", "Elapsed", "Deep", "TimedLogger", "config", "get_logger"]

_ROOT = "scverse"
HINT = (logging.INFO + logging.DEBUG) // 2  # 15; used by the timed logger
logging.addLevelName(HINT, "HINT")


class Rule(logging.Filter):
    """A logging rule — subclass and override what you need; both default to no-ops.

    - :meth:`keep` ``(record) -> bool`` — return ``False`` to drop the record.
    - :meth:`rewrite` ``(message, record) -> str`` — return the new text
      (``message`` is the fully formatted string).

    Rules run in registration order on the shared handler, for every package.
    """

    def keep(self, record: logging.LogRecord) -> bool:
        """Return ``False`` to drop the record (default: keep everything)."""
        return True

    def rewrite(self, message: str, record: logging.LogRecord) -> str:
        """Return the new message text (default: unchanged)."""
        return message

    def filter(self, record: logging.LogRecord) -> bool:  # stdlib hook; don't override
        """Stdlib hook: apply :meth:`keep` then :meth:`rewrite`. Don't override."""
        if not self.keep(record):
            return False
        message = record.getMessage()  # always a str, %-args already expanded
        new = self.rewrite(message, record)
        if new != message:
            record.msg, record.args = new, ()
        return True


class Elapsed(Rule):
    """Render ``record.time_passed`` (a ``timedelta``). Universal, enabled by default."""

    def rewrite(self, message: str, record: logging.LogRecord) -> str:
        """Substitute ``{time_passed}`` if present, else append ``(H:MM:SS)``."""
        td = getattr(record, "time_passed", None)
        if not td:  # None or zero -> show nothing (matches scanpy)
            return message
        td = timedelta(seconds=int(td.total_seconds()))  # strip sub-second noise
        if "{time_passed}" in message:
            return message.replace("{time_passed}", str(td))
        return f"{message} ({td})"


class Deep(Rule):
    """Append ``record.deep`` as detail. Universal, enabled by default."""

    def rewrite(self, message: str, record: logging.LogRecord) -> str:
        """Append ``record.deep`` as ``": detail"`` when present."""
        deep = getattr(record, "deep", None)
        return message if deep is None else f"{message}: {deep}"


def _make_handler(use_rich: bool) -> logging.Handler:
    if use_rich:
        from rich.logging import RichHandler

        return RichHandler(show_path=False, show_time=False)  # rich renders the level itself
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    return handler


def _rich_available() -> bool:
    from importlib.util import find_spec

    return find_spec("rich") is not None


class _Config:
    """Central logging configuration; the singleton instance is :data:`config`."""

    def __init__(self) -> None:
        self._root = logging.getLogger(_ROOT)
        self._root.setLevel(logging.WARNING)
        self._root.propagate = False  # one handler here; don't double-log via root
        self._rich: bool | None = None  # None = auto-detect rich
        self._rules: list[Rule] = [Elapsed(), Deep()]  # universal defaults; order matters
        self._install(_make_handler(self._use_rich()))

    def _install(self, handler: logging.Handler) -> None:
        for r in self._rules:
            handler.addFilter(r)
        self._root.addHandler(handler)

    def _use_rich(self) -> bool:
        return _rich_available() if self._rich is None else self._rich

    @property
    def verbosity(self) -> str | int:
        """Central level for all scverse loggers. Set with a name (``"info"``) or int."""
        return logging.getLevelName(self._root.level)

    @verbosity.setter
    def verbosity(self, level: str | int) -> None:
        self._root.setLevel(level.upper() if isinstance(level, str) else level)

    @property
    def rich(self) -> bool:
        """Whether rich rendering is active. Set ``True``/``False`` to force, ``None`` to auto-detect."""
        return self._use_rich()

    @rich.setter
    def rich(self, enabled: bool | None) -> None:
        self._rich = enabled
        for h in list(self._root.handlers):
            self._root.removeHandler(h)
        self._install(_make_handler(self._use_rich()))

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)
        for h in self._root.handlers:
            h.addFilter(rule)

    def remove_rule(self, rule: Rule) -> None:
        if rule in self._rules:
            self._rules.remove(rule)
        for h in self._root.handlers:
            h.removeFilter(rule)


config = _Config()


class TimedLogger:
    """Opt-in scanpy-style wrapper: ``time=``/``deep=`` keywords + a ``datetime`` return.

    Sets ``time_passed``/``deep`` on the record (rendered by the :class:`Elapsed`
    and :class:`Deep` rules) and returns the current time so callers can thread it.
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
