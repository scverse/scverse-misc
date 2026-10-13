import sys
from functools import cache

import pytest

pytest.importorskip("scverse_misc.sphinx_ext")
from scverse_misc._utils import mark_decorator
from scverse_misc.sphinx_ext import _is_decorator, _member_type


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


def plain_func() -> None: ...


@mark_decorator
def deco() -> None: ...


@mark_decorator
class DecoCls: ...


class DecoSubCls(DecoCls): ...


alias = sys.modules[__name__]


@pytest.mark.parametrize(
    ["attrname", "attrtype"],
    (
        ("attr", "attribute"),
        ("func", "method"),
        ("prop", "property"),
        ("static", "method"),
        ("klass", "method"),
        ("cached", "method"),
    ),
)
def test_member_type(attrname: str, attrtype: str) -> None:
    obj_path = f"{__name__}.DummyCls.{{}}"
    alias_path = f"{__name__}.alias.DummyCls.{{}}"
    assert _member_type(obj_path.format(attrname)) == attrtype
    assert _member_type(alias_path.format(attrname)) == attrtype


@pytest.mark.parametrize(
    ["objname", "is_deco"],
    (
        ("plain_func", False),
        ("deco", True),
        ("DummyCls", False),
        ("DecoCls", True),
        ("DecoSubCls", False),  # the marker must not be inherited
    ),
)
def test_is_decorator(objname: str, is_deco: bool) -> None:
    assert _is_decorator(f"{__name__}.{objname}") == is_deco
    assert _is_decorator(f"{__name__}.alias.{objname}") == is_deco
