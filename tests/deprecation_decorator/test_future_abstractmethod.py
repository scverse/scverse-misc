from __future__ import annotations

from abc import ABC, abstractmethod

import pytest

from scverse_misc import Deprecation, future_abstractmethod


class Base(ABC):
    seen: list[str]

    def __init_subclass__(cls, tag: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.seen = [tag]

    @future_abstractmethod(Deprecation("0.2", "Do it."))
    def foo(self) -> int:
        return 1


def test_warns_without_override() -> None:
    with pytest.warns(FutureWarning, match=r"Missing doesn’t implement Base\.foo.*Do it\.") as record:

        class Missing(Base, tag="x"):
            pass

    assert record[0].filename == __file__
    assert Missing.seen == ["x"]  # original `__init_subclass__` still runs
    assert Missing().foo() == 1  # default implementation still works


def test_no_warning() -> None:
    class Impl(Base):
        def foo(self) -> int:
            return 2

    class ImplChild(Impl):
        pass

    class Intermediate(Base):  # abstract, so not required to implement yet
        @abstractmethod
        def bar(self) -> None: ...

    assert ImplChild().foo() == 2


def test_abc_behavior() -> None:
    class Intermediate(Base):
        @abstractmethod
        def bar(self) -> None: ...

    with pytest.raises(TypeError, match=r"abstract method.*bar"):
        Intermediate()  # type: ignore[abstract]

    with pytest.warns(FutureWarning, match=r"Concrete doesn’t implement Base\.foo"):

        class Concrete(Intermediate):
            def bar(self) -> None: ...

    assert Concrete().foo() == 1
