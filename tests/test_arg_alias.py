import sys
from enum import Enum
from inspect import getsource
from textwrap import dedent
from types import ModuleType
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


class Klass:
    @arg_alias("axis_str")
    @arg_alias("axis")
    def __init__(
        self,
        other: "Klass | None" = None,
        axis: Literal[0, "obs"] | Literal[1, "var"] = 0,
        axis_str: "Literal[0, 'obs'] | Literal[1, 'var']" = 0,
    ) -> None:
        self.axis = axis
        self.axis_str = axis_str


def test_arg_alias_inner_method() -> None:

    obj = Klass(axis="var", axis_str="var")
    assert obj.axis == 1
    assert obj.axis_str == 1

    obj = Klass(axis="obs", axis_str="obs")
    assert obj.axis == 0
    assert obj.axis_str == 0


def test_arg_alias_inner_class_method() -> None:
    class InnerKlass:
        @arg_alias("axis_str")
        @arg_alias("axis")
        def __init__(
            self,
            other: "InnerKlass | None" = None,
            axis: Literal[0, "obs"] | Literal[1, "var"] = 0,
            axis_str: "Literal[0, 'obs'] | Literal[1, 'var']" = 0,
        ) -> None:
            self.axis = axis
            self.axis_str = axis_str

    obj = InnerKlass(axis="var", axis_str="var")
    assert obj.axis == 1
    assert obj.axis_str == 1

    obj = InnerKlass(axis="obs", axis_str="obs")
    assert obj.axis == 0
    assert obj.axis_str == 0


def test_arg_alias_inner_class_return_method() -> None:
    def make_class() -> type:
        class InnerKlass:
            @arg_alias("axis_str")
            @arg_alias("axis")
            def __init__(
                self,
                other: "InnerKlass | None" = None,
                axis: Literal[0, "obs"] | Literal[1, "var"] = 0,
                axis_str: "Literal[0, 'obs'] | Literal[1, 'var']" = 0,
            ) -> None:
                self.axis = axis
                self.axis_str = axis_str

        return InnerKlass

    klass = make_class()

    obj = klass(axis="var", axis_str="var")
    assert obj.axis == 1
    assert obj.axis_str == 1

    obj = klass(axis="obs", axis_str="obs")
    assert obj.axis == 0
    assert obj.axis_str == 0


# unrealistic example, real code would use a StrEnum and `color = Color(color)` for this use case
class Color(Enum):
    RED = 1
    GREEN = 2


HINT = "Literal[Color.RED, 'red'] | Literal[Color.GREEN, 'green']"
HINT_TC = HINT.replace("Literal", "typing.Literal")  # as if `typing` was imported under `TYPE_CHECKING`
lazy_annots = pytest.mark.skipif(sys.version_info < (3, 14), reason="unresolvable annotations need PEP 649")


@pytest.mark.parametrize(
    "src",
    [
        # the `NeverDefined` sibling makes `get_type_hints` fail forever, not just before `Color` exists
        pytest.param(f'def obj(color: "{HINT}", other: "NeverDefined" = None): return color', id="str"),
        pytest.param(f"def obj(color: {HINT}): return color", id="forwardref_in_literal", marks=lazy_annots),
        pytest.param("def obj(color: ColorHint): return color", id="forwardref_whole_hint", marks=lazy_annots),
        pytest.param(
            f"def obj(color: {HINT}, other: NeverDefined = None): return color",
            id="unresolvable_sibling",
            marks=lazy_annots,
        ),
        pytest.param(
            f'class Holder:\n color: "{HINT_TC}"\n def __init__(self, color): self.color = color\n'
            "obj = lambda color: Holder(color).color",
            id="class",
        ),
    ],
)
def test_arg_alias_deferred(src: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The annotation is unresolvable at decoration time, only at call time."""
    mod = ModuleType("deferred_mod")
    ns = mod.__dict__
    ns.update(arg_alias=arg_alias, Literal=Literal)
    monkeypatch.setitem(sys.modules, mod.__name__, mod)  # a class resolves its hints via sys.modules
    exec(f"@arg_alias('color')\n{src}", ns)
    # only now the hint becomes resolvable
    ns.update(Color=Color, ColorHint=Literal[Color.RED, "red"] | Literal[Color.GREEN, "green"])

    assert ns["obj"]("red") is Color.RED
    assert ns["obj"](Color.RED) is Color.RED
    assert ns["obj"]("green") is Color.GREEN

    with pytest.raises(ValueError, match="must be one of "):
        ns["obj"]("blue")


def test_arg_alias_raises() -> None:
    with pytest.raises(TypeError, match="must be 'Union' or 'Literal'"):

        @arg_alias("axis")
        def func(axis: int) -> None:
            pass

    with pytest.raises(TypeError, match="must be 'Literal'"):

        @arg_alias("axis")
        def func(axis: Literal[0, "obs"] | int) -> None:
            pass
