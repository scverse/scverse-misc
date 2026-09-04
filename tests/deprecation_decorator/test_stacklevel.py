"""The warning must be blamed on the caller, however many decorators are stacked in between."""

from __future__ import annotations

import inspect
import sys

import pytest
from depkg import DepABC, DepClass, dep_arg_explicit_stacklevel, dep_arg_func, dep_dispatch, dep_func


# Calls go directly in the test body: a `lambda` in a fixture or `parametrize` would be
# the caller, so blaming *it* would be correct and the test would prove nothing.
@pytest.mark.xfail(reason="`warnings.deprecated` warns itself, at a fixed level: python/cpython#156929")
def test_deprecated_blames_caller() -> None:
    with pytest.warns(FutureWarning, match="is deprecated") as record:
        expected = sys._getframe().f_lineno + 1
        dep_func()
    assert (record[0].filename, record[0].lineno) == (__file__, expected)


def test_deprecated_arg_blames_caller() -> None:
    with pytest.warns(FutureWarning, match="bar is deprecated") as record:
        expected = sys._getframe().f_lineno + 1
        dep_arg_func(bar=3)
    assert (record[0].filename, record[0].lineno) == (__file__, expected)


def test_stdlib_wrapper_blames_caller() -> None:
    with pytest.warns(FutureWarning, match="bar is deprecated") as record:
        expected = sys._getframe().f_lineno + 1
        dep_dispatch(1, bar=2)
    assert (record[0].filename, record[0].lineno) == (__file__, expected)


def test_explicit_stacklevel_still_honored() -> None:
    with pytest.warns(FutureWarning) as record:
        expected = sys._getframe().f_lineno + 1
        dep_arg_explicit_stacklevel(bar=2)
    assert (record[0].filename, record[0].lineno) == (__file__, expected)


def test_deprecated_class_stays_a_class() -> None:
    with pytest.warns(FutureWarning, match="The class DepClass is deprecated"):
        obj = DepClass(1)
    assert isinstance(obj, DepClass) and obj.x == 1


def test_deprecated_class_instantiation_blames_caller() -> None:
    with pytest.warns(FutureWarning) as record:
        expected = sys._getframe().f_lineno + 1
        DepClass(1)
    assert (record[0].filename, record[0].lineno) == (__file__, expected)


def test_deprecated_class_subclassing_blames_caller() -> None:
    with pytest.warns(FutureWarning) as record:

        class Sub(DepClass): ...

    expected = inspect.getsourcelines(Sub)[1]
    assert (record[0].filename, record[0].lineno) == (__file__, expected)


@pytest.mark.xfail(reason="`warnings.deprecated` warns itself, at a fixed level: python/cpython#156929")
def test_deprecated_class_with_metaclass_subclassing_blames_caller() -> None:
    with pytest.warns(FutureWarning) as record:

        class Sub(DepABC): ...

    expected = inspect.getsourcelines(Sub)[1]
    assert (record[0].filename, record[0].lineno) == (__file__, expected)
