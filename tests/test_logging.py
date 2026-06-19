from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from scverse_misc import logging as mod
from scverse_misc.logging import Deep, Elapsed, Rule, TimedLogger, config, get_logger

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def sink() -> Generator[io.StringIO, None, None]:
    """Force the plain handler, capture its output, and restore global state after."""
    old_level = config._root.level
    old_rules = list(config._rules)
    config.rich = False
    handler = config._root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    buf = io.StringIO()
    handler.setStream(buf)
    config.verbosity = "debug"
    try:
        yield buf
    finally:
        # drop any rules a test added, then restore level + a clean plain handler
        for rule in list(config._rules):
            if rule not in old_rules:
                config.remove_rule(rule)
        config._root.setLevel(old_level)


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


def test_elapsed_substitution_and_append(sink: io.StringIO) -> None:
    log = get_logger("selftest", timed=True)
    now = datetime.now()
    log.info("finished ({time_passed})", time=now - timedelta(seconds=5))
    log.info("done", time=now - timedelta(seconds=2))
    out = sink.getvalue()
    assert "finished (0:00:05)" in out
    assert "done (0:00:02)" in out


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
    # 0 must not be dropped by a truthiness check (Deep uses `is None`)
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


def test_user_rule_composes_and_verbosity_gates(sink: io.StringIO) -> None:
    class Tag(Rule):
        def rewrite(self, message: str, record: logging.LogRecord) -> str:
            return f"[{record.name.rsplit('.', 1)[-1]}] {message}"

    config.add_rule(Tag())
    log = get_logger("selftest", timed=True)
    log.warning("hi")
    assert "[selftest] hi" in sink.getvalue()


def test_rule_keep_can_drop_record(sink: io.StringIO) -> None:
    class DropAll(Rule):
        def keep(self, record: logging.LogRecord) -> bool:
            return False

    config.add_rule(DropAll())
    get_logger("selftest").warning("should be dropped")
    assert sink.getvalue() == ""


def test_base_rule_is_passthrough(sink: io.StringIO) -> None:
    config.add_rule(Rule())  # base keep()/rewrite() are no-ops
    get_logger("selftest").warning("unchanged")
    assert "unchanged" in sink.getvalue()


def test_verbosity_get_set_by_name_and_int() -> None:
    config.verbosity = "warning"
    assert config.verbosity == "WARNING"
    plain = get_logger("selftest")
    assert not plain.isEnabledFor(logging.INFO)
    assert plain.isEnabledFor(logging.WARNING)
    config.verbosity = logging.DEBUG
    assert plain.isEnabledFor(logging.DEBUG)


def test_universal_rules_enabled_by_default() -> None:
    assert any(isinstance(r, Elapsed) for r in config._rules)
    assert any(isinstance(r, Deep) for r in config._rules)


def test_hint_level_registered() -> None:
    assert logging.getLevelName(mod.HINT) == "HINT"


def test_remove_rule_is_idempotent() -> None:
    rule = Rule()
    config.add_rule(rule)
    config.remove_rule(rule)
    config.remove_rule(rule)  # removing again must not raise
    assert rule not in config._rules


def test_all_level_methods_emit_and_return_datetime(sink: io.StringIO) -> None:
    log = get_logger("selftest", timed=True)
    for emit in (log.debug, log.hint, log.info, log.warning, log.error, log.critical):
        assert isinstance(emit("msg"), datetime)


def test_timed_logger_delegates_unknown_attrs() -> None:
    log = get_logger("selftest", timed=True)
    # name / getEffectiveLevel aren't defined on TimedLogger -> __getattr__ delegates
    assert log.name == "scverse.selftest"
    assert log.getEffectiveLevel() == logging.getLogger("scverse.selftest").getEffectiveLevel()


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
