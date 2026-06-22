from __future__ import annotations

from textwrap import indent
from typing import TYPE_CHECKING

import pytest

from scverse_misc import Deprecation, deprecated_arg

if TYPE_CHECKING:
    from collections.abc import Callable


def test_deprecation_decorator(deprecated_func: Callable[..., int], msg: str | None) -> None:
    msg = indent(msg, "    ") if isinstance(msg, str) and "\n" in msg else (msg or "")
    with pytest.warns(FutureWarning, match=rf"(?s)is deprecated.*{msg}"):
        assert deprecated_func(1, 2, 3, keyword_only_default=4.0) == 42


@pytest.mark.parametrize(
    "arg",
    ("positional_only_no_default", "positional_only_default", "positional_or_keyword_default", "keyword_only_default"),
)
def test_deprecated_arg_decorator(func: Callable[..., int], msg: str | None, arg: str) -> None:
    deprecated_func = deprecated_arg(arg, Deprecation("2.718", msg or ""))(func)
    with pytest.warns(FutureWarning, match=rf"{arg} is deprecated.*{msg or ''}"):
        assert deprecated_func(1, 2, 3, keyword_only_default=4.0) == 42
