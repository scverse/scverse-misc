from typing import Literal

import pytest

from scverse_misc import arg_alias


def test_arg_alias() -> None:
    @arg_alias("axis_union")
    @arg_alias("axis")
    def func(
        x: float,
        axis: Literal[0, "obs", "samples"],
        y: float = 2,
        axis_union: Literal[0, "obs"] | Literal[1, "var", "features"] = "var",
    ) -> tuple[float, float]:
        assert axis == 0
        assert axis_union in (0, 1)

        return x * axis, y * axis_union

    assert func(42, 0) == (0, 2)
    assert func(42, "obs") == (0, 2)
    assert func(42, "samples", 3) == (0, 3)
    assert func(42, 0, axis_union="obs") == (0, 0)
    assert func(42, 0, axis_union="features") == (0, 2)
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
