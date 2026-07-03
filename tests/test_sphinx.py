from functools import cache

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

    @staticmethod
    def static() -> float:
        return 2.71

    @classmethod
    def klass(cls) -> float:
        return 1.61

    @cache  # noqa: B019
    def cached(self) -> float:
        return 4.13


def test_member_type() -> None:
    obj_path = f"{__name__}.DummyCls.{{}}"
    assert _member_type(obj_path.format("attr")) == "attribute"
    assert _member_type(obj_path.format("func")) == "method"
    assert _member_type(obj_path.format("prop")) == "property"
    assert _member_type(obj_path.format("static")) == "method"
    assert _member_type(obj_path.format("klass")) == "method"
    assert _member_type(obj_path.format("cached")) == "method"
