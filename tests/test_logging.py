from __future__ import annotations

import io
import logging
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

try:  # the config's pydantic tier (and these assertions) need pydantic
    from pydantic import ValidationError
except ImportError:
    pytest.skip("logging config's pydantic tier needs pydantic", allow_module_level=True)

from scverse_misc import logging as mod
from scverse_misc.logging import TimedLogger, config, get_logger

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def sink() -> Generator[io.StringIO, None, None]:
    """Force the plain handler, capture its output, and restore global state after."""
    old_level = config._root.level
    old_filters = list(config._filters)
    old_rich = config.rich
    config.rich = False
    handler = config._root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    buf = io.StringIO()
    handler.setStream(buf)
    config.verbosity = "debug"
    try:
        yield buf
    finally:
        # drop any filters a test added, then restore level + rich (reinstalls a clean handler)
        for f in list(config._filters):
            if f not in old_filters:
                config.remove_filter(f)
        config._root.setLevel(old_level)
        config.rich = old_rich
        restored = config._root.handlers[0]
        if isinstance(restored, logging.StreamHandler):
            restored.setStream(sys.stderr)  # drop the dead StringIO the test wrote into


def test_get_logger_plain_naming() -> None:
    plain = get_logger("selftest")
    assert isinstance(plain, logging.Logger)
    assert plain.name == "scverse.selftest"
    assert plain.parent is not None and plain.parent.name == "scverse"


def test_get_logger_does_not_double_prefix() -> None:
    assert get_logger("scverse.already").name == "scverse.already"


def test_timed_logger_returns_datetime(sink: io.StringIO) -> None:
    log = get_logger("selftest", timed=True)
    assert isinstance(log, TimedLogger)
    t = log.info("start")
    assert isinstance(t, datetime)


def test_elapsed_appended(sink: io.StringIO) -> None:
    log = get_logger("selftest", timed=True)
    log.info("done", time=datetime.now() - timedelta(seconds=2))
    assert "done (0:00:02)" in sink.getvalue()


def test_elapsed_noop_without_time(sink: io.StringIO) -> None:
    log = get_logger("selftest", timed=True)
    log.info("plain message")
    out = sink.getvalue()
    assert "plain message" in out
    assert "(" not in out.split("plain message", 1)[1]


def test_deep_appended(sink: io.StringIO) -> None:
    log = get_logger("selftest", timed=True)
    log.info("normalized", deep="3 cells dropped")
    assert "normalized: 3 cells dropped" in sink.getvalue()


def test_deep_falsy_zero_preserved(sink: io.StringIO) -> None:
    # 0 must not be dropped by a truthiness check (`is None`)
    log = get_logger("selftest", timed=True)
    log.info("count", deep=0)
    assert "count: 0" in sink.getvalue()


def test_deep_hidden_when_not_below_level(sink: io.StringIO) -> None:
    # deep only renders when the effective level is strictly below the call level
    config.verbosity = "info"
    log = get_logger("selftest", timed=True)
    log.info("msg", deep="hidden detail")
    out = sink.getvalue()
    assert "msg" in out
    assert "hidden detail" not in out


def test_user_filter_can_drop_record(sink: io.StringIO) -> None:
    class DropAll(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return False

    config.add_filter(DropAll())
    get_logger("selftest").warning("should be dropped")
    assert sink.getvalue() == ""


def test_record_message_is_not_rewritten(sink: io.StringIO) -> None:
    # context stays in record attributes; a second (e.g. JSON) handler sees the raw message
    seen: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record)

    config._root.addHandler(cap := Capture())
    try:
        log = get_logger("selftest", timed=True)
        log.info("finished %s", "step", time=datetime.now() - timedelta(seconds=3), deep="x")
    finally:
        config._root.removeHandler(cap)
    (rec,) = seen
    assert rec.getMessage() == "finished step"
    assert rec.args == ("step",)
    assert isinstance(rec.time_passed, timedelta)  # type: ignore[attr-defined]
    assert rec.deep == "x"  # type: ignore[attr-defined]
    assert "finished step (0:00:03): x" in sink.getvalue()


def test_verbosity_get_set_by_name_and_int() -> None:
    config.verbosity = "warning"
    assert config.verbosity == "WARNING"
    plain = get_logger("selftest")
    assert not plain.isEnabledFor(logging.INFO)
    assert plain.isEnabledFor(logging.WARNING)
    config.verbosity = logging.DEBUG
    assert plain.isEnabledFor(logging.DEBUG)


def test_verbosity_default_is_canonical() -> None:
    # pydantic tier must canonicalize its default too (regression: used to report lowercase "warning")
    assert mod._LogConfig().verbosity == "WARNING"
    config.verbosity = "warning"  # construction re-applied to the shared logger; leave a known state


def test_verbosity_rejects_unknown_level() -> None:
    config.verbosity = "warning"
    for bad in ("bogus", 999):
        with pytest.raises(ValidationError):
            config.verbosity = bad
    assert config.verbosity == "WARNING"  # rejected assignment leaves the value untouched


def test_extras_filter_installed_by_default() -> None:
    assert any(isinstance(f, mod._Extras) for f in config._filters)


def test_hint_level_registered() -> None:
    assert logging.getLevelName(mod.HINT) == "HINT"


def test_remove_filter_is_idempotent() -> None:
    f = logging.Filter()
    config.add_filter(f)
    config.remove_filter(f)
    config.remove_filter(f)  # removing again must not raise
    assert f not in config._filters


def test_all_level_methods_emit_and_return_datetime(sink: io.StringIO) -> None:
    log = get_logger("selftest", timed=True)
    for emit in (log.debug, log.hint, log.info, log.warning, log.error, log.critical):
        assert isinstance(emit("msg"), datetime)


def test_timed_logger_delegates_unknown_attrs() -> None:
    log = get_logger("selftest", timed=True)
    # name / getEffectiveLevel aren't defined on TimedLogger -> __getattr__ delegates
    assert log.name == "scverse.selftest"
    assert log.getEffectiveLevel() == logging.getLogger("scverse.selftest").getEffectiveLevel()


def test_reduced_tier_without_pydantic(monkeypatch: pytest.MonkeyPatch) -> None:
    """With pydantic absent, logging falls back to the stdlib config tier."""
    import importlib.util
    import sys

    root = logging.getLogger("scverse")
    saved_handlers, saved_level = list(root.handlers), root.level

    # Load a *fresh, isolated* copy of the module with pydantic unavailable. Reloading
    # scverse_misc.logging in place would rebind its classes, breaking other tests'
    # already-bound `from scverse_misc.logging import TimedLogger` references.
    monkeypatch.setitem(sys.modules, "pydantic", None)
    spec = importlib.util.spec_from_file_location("scverse_misc._logging_nopydantic", mod.__file__)
    assert spec is not None and spec.loader is not None
    reduced = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(reduced)  # its `config = _LogConfig()` mutates the shared logger
        assert reduced._HAVE_PYDANTIC is False

        cfg = reduced.config
        assert cfg.rich is None  # default matches the full tier (None = auto-detect)

        cfg.verbosity = "info"
        assert cfg.verbosity == "INFO"
        for bad in ("bogus", 999):  # reduced tier validates too (raises ValueError, not ValidationError)
            with pytest.raises(ValueError):
                cfg.verbosity = bad
        assert cfg.verbosity == "INFO"  # rejected assignment leaves the value untouched

        tag = logging.Filter()
        cfg.add_filter(tag)
        cfg.add_filter(tag)  # handler dedups; must not leave a phantom copy
        cfg.remove_filter(tag)
        assert tag not in cfg._filters  # regression: reduced tier used to resurrect removed filters
    finally:
        monkeypatch.undo()
        root.handlers[:] = saved_handlers  # undo the shared-logger mutation from loading `reduced`
        root.setLevel(saved_level)


def test_rich_property_installs_rich_handler() -> None:
    pytest.importorskip("rich")
    from rich.logging import RichHandler

    try:
        config.rich = True
        assert isinstance(config._root.handlers[0], RichHandler)
        assert config.rich is True
    finally:
        config.rich = False
        assert config.rich is False
