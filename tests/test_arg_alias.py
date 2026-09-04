from typing import Literal

import pytest

from scverse_misc import arg_alias


def test_arg_alias() -> None:
    @arg_alias("axis_union_string")
    @arg_alias("axis_union")
    @arg_alias("axis")
    def func(
        x: float,
        axis: Literal[0, "obs", "samples"],
        y: float = 2,
        axis_union: Literal[0, "obs"] | Literal[1, "var", "features"] = "var",
        axis_union_string: "Literal[0, 'obs'] | Literal[1, 'var', 'vars']" = "vars",
    ) -> tuple[int, int, int]:
        assert axis == 0
        assert axis_union in (0, 1)
        assert axis_union_string in (0, 1)

        return axis, axis_union, axis_union_string

    assert func(42, 0) == (0, 1, 1)
    assert func(42, "obs") == (0, 1, 1)
    assert func(42, "samples", 3) == (0, 1, 1)
    assert func(42, 0, axis_union="obs", axis_union_string="obs") == (0, 0, 0)
    assert func(42, 0, axis_union="features", axis_union_string="vars") == (0, 1, 1)
    assert func(42, 0, axis_union=0, axis_union_string=0) == (0, 0, 0)

    with pytest.raises(ValueError, match="must be one of "):
        func(42, "obs", axis_union="vars")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="must be one of "):
        func(42, "obs", axis_union_string="features")  # type: ignore[arg-type]


def test_arg_alias_raises() -> None:
    with pytest.raises(TypeError, match="must be 'Union' or 'Literal'"):

        @arg_alias("axis")
        def func(axis: int) -> None:
            pass

    with pytest.raises(TypeError, match="must be 'Literal'"):

        @arg_alias("axis")
        def func(axis: Literal[0, "obs"] | int) -> None:
            pass
