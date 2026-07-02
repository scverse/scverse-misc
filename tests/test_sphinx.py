import pytest

pytest.importorskip("scverse_misc.sphinx_ext")
from scverse_misc.sphinx_ext import _member_type


class DummyCls:
    attr: float

    def __init__(self) -> None:
        self.attr = 3.14

    def func(self) -> int:
        return 42

    @property
    def prop(self) -> int:
        return 1337


def test_member_type() -> None:
    obj_path = f"{__name__}.DummyCls.{{}}"
    assert _member_type(obj_path.format("attr")) == "attribute"
    assert _member_type(obj_path.format("func")) == "method"
    assert _member_type(obj_path.format("prop")) == "property"
