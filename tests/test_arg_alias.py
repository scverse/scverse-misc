from inspect import getsource
from textwrap import dedent
from typing import TYPE_CHECKING, Literal

import pytest

from scverse_misc import arg_alias


@pytest.mark.parametrize("stringify", [True, False], ids=["stringify", "no_stringify"])
def test_arg_alias(stringify: bool) -> None:
    @arg_alias("axis_union")
    @arg_alias("axis")
    def func(
        x: float,
        axis: Literal[0, "obs", "samples"],
        y: float = 2,
        axis_union: Literal[0, "obs"] | Literal[1, "var", "features"] = "var",
    ) -> tuple[int, int]:
        assert axis == 0
        assert axis_union in (0, 1)

        return axis, axis_union

    if stringify:
        ns: dict[str, object] = {}
        exec(f"from __future__ import annotations\n{dedent(getsource(func))}", globals(), ns)
        if not TYPE_CHECKING:  # shhh
            func = ns["func"]
    assert isinstance(func.__annotations__["return"], str) == stringify

    assert func(42, 0) == (0, 1)
    assert func(42, "obs") == (0, 1)
    assert func(42, "samples", 3) == (0, 1)
    assert func(42, 0, axis_union="obs") == (0, 0)
    assert func(42, 0, axis_union="features") == (0, 1)
    assert func(42, 0, axis_union=0) == (0, 0)

    with pytest.raises(ValueError, match="must be one of "):
        func(42, "obs", axis_union="vars")  # type: ignore[arg-type]


def test_arg_alias_raises() -> None:
    with pytest.raises(TypeError, match="must be 'Union' or 'Literal'"):

        @arg_alias("axis")
        def func(axis: int) -> None:
            pass

    with pytest.raises(TypeError, match="must be 'Literal'"):

        @arg_alias("axis")
        def func(axis: Literal[0, "obs"] | int) -> None:
            pass
