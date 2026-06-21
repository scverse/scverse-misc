from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from scverse_misc import Deprecation, deprecated


@pytest.fixture(
    params=[
        pytest.param(None, id="no_message"),
        pytest.param("Test message.", id="short_message"),
        pytest.param("Test\nmessage.", id="long_message"),
    ]
)
def msg(request: pytest.FixtureRequest) -> str | None:
    return cast(str | None, request.param)


@pytest.fixture(scope="session")
def docstring() -> str | None:
    return None  # gets overridden in `test_sphinx.py`


@pytest.fixture
def func(docstring: str | None) -> Callable[..., int]:
    def _func(
        positional_only_no_default: int,
        positional_only_default: int = 1337,
        /,
        positional_or_keyword_default: int = 42,
        *,
        keyword_only_default: float = 3.1415,
    ) -> int:
        return 42

    _func.__doc__ = docstring
    return _func


@pytest.fixture
def deprecated_func(msg: str | None, func: Callable[..., int]) -> Callable[..., int]:
    return deprecated(Deprecation("foo", msg or ""))(func)
