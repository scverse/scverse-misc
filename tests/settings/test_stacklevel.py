"""`__init_subclass__` runs under two metaclass frames, so no fixed `stacklevel` reaches the `class` statement."""

from __future__ import annotations

import inspect
import warnings

from scverse_misc import Settings


def test_subclass_warning_blames_class_statement() -> None:
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")

        class MySettings(Settings, exported_object_name="settings"): ...

    expected = inspect.getsourcelines(MySettings)[1]
    assert [(w.filename, w.lineno) for w in record] == [(__file__, expected)]
