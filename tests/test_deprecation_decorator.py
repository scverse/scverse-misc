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


@pytest.fixture(
    params=[
        pytest.param(None, id="no_docstring"),
        pytest.param("Test function", id="short"),
        pytest.param(
            """Test function

            This is a test.

            Parameters
            ----------
            foo
                bar
            bar
                baz
            """,
            id="long",
        ),
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
    offset = 0 if docstring is None else 2

    if docstring is not None:
        lines_orig = docstring.expandtabs().splitlines()
        assert lines[0] == lines_orig[0]
        assert len(lines[1].strip()) == 0, "expected empty line following summary"

    assert lines[offset].startswith(".. version-deprecated")
    if msg is None:
        assert len(lines) == offset + 1 or not lines[offset + 1].startswith("   ")
    else:
        msg_lines = msg.splitlines()
        msg_indented = [f"   {line}" for line in msg_lines]
        assert lines[offset + 1 : offset + 1 + len(msg_lines)] == msg_indented
