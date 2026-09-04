"""`__init_subclass__` runs under two metaclass frames, so no fixed `stacklevel` reaches the `class` statement."""

from __future__ import annotations

import inspect

import pytest

from scverse_misc import Settings


def test_subclass_warning_blames_class_statement() -> None:
    with pytest.warns(DeprecationWarning) as warns:

        class MySettings(Settings, exported_object_name="settings"): ...

    expected = inspect.getsourcelines(MySettings)[1]
    assert [(w.filename, w.lineno) for w in warns] == [(__file__, expected)]
