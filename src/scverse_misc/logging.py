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
    t = log.info("normalizing")        # returns a datetime
    log.info("finished ({time_passed})", time=t)   # Elapsed rule renders it
    log.info("done", time=t, deep="42 cells dropped")
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

__all__ = ["Rule", "Elapsed", "Deep", "config", "get_logger"]

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
        return True

    def rewrite(self, message: str, record: logging.LogRecord) -> str:
        return message

    def filter(self, record: logging.LogRecord) -> bool:  # stdlib hook; don't override
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
        self._parent = logging.getLogger(_ROOT)
        self._parent.setLevel(logging.WARNING)
        self._parent.propagate = False  # one handler here; don't double-log via root
        self._rules: list = [Elapsed(), Deep()]  # universal defaults; order matters
        self._install(_make_handler(_rich_available()))

    def _install(self, handler: logging.Handler) -> None:
        for r in self._rules:
            handler.addFilter(r)
        self._parent.addHandler(handler)

    @property
    def verbosity(self):
        """Central level for all scverse loggers. Set with a name (``"info"``) or int."""
        return logging.getLevelName(self._parent.level)

    @verbosity.setter
    def verbosity(self, level) -> None:
        self._parent.setLevel(level.upper() if isinstance(level, str) else level)

    def use_rich(self, enabled: bool = True) -> None:
        """Force the rich (``True``) or plain (``False``) handler."""
        for h in list(self._parent.handlers):
            self._parent.removeHandler(h)
        self._install(_make_handler(enabled))

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)
        for h in self._parent.handlers:
            h.addFilter(rule)

    def remove_rule(self, rule: Rule) -> None:
        if rule in self._rules:
            self._rules.remove(rule)
        for h in self._parent.handlers:
            h.removeFilter(rule)


config = _Config()


class _TimedLogger:
    """Opt-in scanpy-style wrapper: ``time=``/``deep=`` keywords + a ``datetime`` return.

    Sets ``time_passed``/``deep`` on the record (rendered by the :class:`Elapsed`
    and :class:`Deep` rules) and returns the current time so callers can thread it.
    Everything else delegates to the underlying real logger.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def __getattr__(self, name):
        if name == "_logger":
            raise AttributeError(name)
        return getattr(self._logger, name)

    def _emit(self, level, msg, *args, time=None, deep=None, **kw) -> datetime:
        now = datetime.now()
        if self._logger.isEnabledFor(level):
            extra = dict(kw.pop("extra", None) or {})
            if time is not None:
                extra["time_passed"] = now - time  # thread the returned value (both naive)
            if deep is not None and self._logger.getEffectiveLevel() < level:
                extra["deep"] = deep
            kw["stacklevel"] = kw.get("stacklevel", 1) + 2  # skip _emit + the level method
            self._logger.log(level, msg, *args, extra=extra, **kw)
        return now

    def debug(self, msg, *a, **k) -> datetime:
        return self._emit(logging.DEBUG, msg, *a, **k)

    def hint(self, msg, *a, **k) -> datetime:
        return self._emit(HINT, msg, *a, **k)

    def info(self, msg, *a, **k) -> datetime:
        return self._emit(logging.INFO, msg, *a, **k)

    def warning(self, msg, *a, **k) -> datetime:
        return self._emit(logging.WARNING, msg, *a, **k)

    def error(self, msg, *a, **k) -> datetime:
        return self._emit(logging.ERROR, msg, *a, **k)

    def critical(self, msg, *a, **k) -> datetime:
        return self._emit(logging.CRITICAL, msg, *a, **k)


def get_logger(name: str, *, timed: bool = False):
    """Return the ``scverse.<name>`` logger a package should use.

    ``timed=False`` (default) returns a plain :class:`logging.Logger`.
    ``timed=True`` returns a :class:`_TimedLogger` with scanpy-style ``time=`` /
    ``deep=`` keywords and a ``datetime`` return.
    """
    logger = logging.getLogger(name if name.startswith(f"{_ROOT}.") else f"{_ROOT}.{name}")
    return _TimedLogger(logger) if timed else logger


if __name__ == "__main__":
    # ponytail: one runnable check. `python -m scverse_misc.logging`.
    import io

    # capture the shared handler's output via a plain formatter we control
    config.use_rich(False)
    buf = io.StringIO()
    config._parent.handlers[0].setStream(buf)  # type: ignore[attr-defined]
    config.verbosity = "debug"

    plain = get_logger("selftest")
    assert plain.name == "scverse.selftest" and plain.parent.name == "scverse"
    assert isinstance(plain, logging.Logger)  # real logger: critical/getChild/etc. work

    log = get_logger("selftest", timed=True)
    t = log.info("start")
    assert isinstance(t, datetime)

    # {time_passed} substitution + append, via the Elapsed rule (works rich or plain)
    log.info("finished ({time_passed})", time=t - timedelta(seconds=5))
    log.info("done", time=t - timedelta(seconds=2))
    # deep, via the Deep rule (shown because verbosity debug < info level)
    log.info("normalized", deep="3 cells dropped")
    out = buf.getvalue()
    assert "finished (0:00:05)" in out, out
    assert "done (0:00:02)" in out, out
    assert "normalized: 3 cells dropped" in out, out

    # falsy deep is preserved (not dropped by a truthiness check)
    buf.truncate(0); buf.seek(0)
    log.info("count", deep=0)
    assert "count: 0" in buf.getvalue(), buf.getvalue()

    # a user Rule composes with the defaults; central verbosity gates output
    class Tag(Rule):
        def rewrite(self, message, record):
            return f"[{record.name.rsplit('.', 1)[-1]}] {message}"

    tag = Tag()
    config.add_rule(tag)
    buf.truncate(0); buf.seek(0)
    log.warning("hi")
    assert "[selftest] hi" in buf.getvalue(), buf.getvalue()
    config.remove_rule(tag)

    config.verbosity = "warning"
    assert not plain.isEnabledFor(logging.INFO) and plain.isEnabledFor(logging.WARNING)

    print("ok")
