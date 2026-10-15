"""Stand-in for a package that deprecates things. Must be a different package from its caller."""

from __future__ import annotations

from abc import ABC
from functools import singledispatch, wraps
from typing import TYPE_CHECKING

from scverse_misc import Deprecation, deprecated, deprecated_arg

if TYPE_CHECKING:
    from collections.abc import Callable


def hidden_decorator[F: Callable[..., object]](func: F) -> F:
    """A wrapper frame that opts out via `__tracebackhide__`, like `legacy_api_wrap`."""

    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        __tracebackhide__ = True
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def plain_decorator[F: Callable[..., object]](func: F) -> F:
    """A wrapper frame in the deprecating package itself, marking nothing."""

    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


@hidden_decorator
@plain_decorator
@deprecated(Deprecation("0.2", "Use bar() instead."))
def dep_func() -> None:
    pass


@hidden_decorator
@plain_decorator
@deprecated_arg("bar", Deprecation("0.2", "Use baz instead."))
def dep_arg_func(*, bar: int = 1, baz: int = 2) -> None:
    pass


@singledispatch  # stdlib wrapper frame
@deprecated_arg("bar", Deprecation("0.2"))
def dep_dispatch(_x: object, *, bar: int = 1) -> None:
    pass


@deprecated_arg("bar", Deprecation("0.2"), stacklevel=1)
def dep_arg_explicit_stacklevel(*, bar: int = 1) -> None:
    pass


@deprecated(Deprecation("0.2"))
class DepClass:
    def __init__(self, x: int) -> None:
        self.x = x


@deprecated(Deprecation("0.2"))
class DepABC(ABC):  # Python-level metaclass => extra frames on subclassing  # noqa: B024
    pass
