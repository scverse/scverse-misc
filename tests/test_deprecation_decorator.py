from collections.abc import Callable
from typing import cast

import pytest

from scverse_misc import Deprecation, deprecated


@pytest.fixture(params=[None, "Test message."])
def msg(request: pytest.FixtureRequest) -> str | None:
    return cast(str | None, request.param)


@pytest.fixture(
    params=[
        None,
        "Test function",
        """Test function

    This is a test.

    Parameters
    ----------
    foo
        bar
    bar
        baz
""",
    ]
)
def docstring(request: pytest.FixtureRequest) -> str | None:
    return cast(str | None, request.param)


@pytest.fixture
def deprecated_func(msg: str | None, docstring: str | None) -> Callable[[int, int], int]:
    def func(foo: int, bar: int) -> int:
        return 42

    func.__doc__ = docstring
    return deprecated(Deprecation("foo", msg or ""))(func)


def test_deprecation_decorator(
    deprecated_func: Callable[[int, int], int], docstring: str | None, msg: str | None
) -> None:
    with pytest.warns(FutureWarning, match="deprecated"):
        assert deprecated_func(1, 2) == 42

    assert deprecated_func.__doc__ is not None
    lines = deprecated_func.__doc__.expandtabs().splitlines()
    if docstring is None:
        assert lines[0].startswith(".. version-deprecated::")
    else:
        lines_orig = docstring.expandtabs().splitlines()
        assert lines[0] == lines_orig[0]
        assert len(lines[1].strip()) == 0
        assert lines[2].startswith(".. version-deprecated")
        if msg is None:
            assert len(lines) == 3
        else:
            assert lines[3] == f"   {msg}"
