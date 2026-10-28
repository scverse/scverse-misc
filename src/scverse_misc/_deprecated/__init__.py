from __future__ import annotations

import inspect
from functools import wraps
from typing import TYPE_CHECKING, LiteralString, Protocol, cast
from warnings import warn

from .._utils import caller_skip_prefixes, warn_outside
from ..constants import ATTR_DEPRECATED_ARG

if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["deprecated", "deprecated_arg", "future_abstractmethod", "Deprecation"]


if TYPE_CHECKING:
    from .decorator import _deprecated as deprecated
else:
    from .decorator import deprecated


class Deprecation(str):
    """Utility class storing information on deprecated functionality.

    Args:
        version_deprecated: The version of the package where the functionality was deprecated.
        msg: The deprecation message.

    .. seealso::
       :ref:`example-deprecating-a-function`, :ref:`example-deprecating-a-function-argument`, :ref:`example-settings-class`
    """

    version_deprecated: LiteralString
    _docmsg: str | None = None

    def __new__(cls, version_deprecated: LiteralString, msg: LiteralString = "") -> Deprecation:
        if not msg:
            msg = ""  # be lenient here, people don’t want to see “None” or “False” here
        obj = super().__new__(cls, msg)
        obj.version_deprecated = version_deprecated
        return obj


class CallableWithDeprecatedArg[**P, R](Protocol):
    __scverse_misc_deprecated_arg__: list[deprecated_arg]

    def __call__(*args: P.args, **kwargs: P.kwargs) -> R: ...


class deprecated_arg:
    """Decorator to indicate that a function argument is deprecated.

    Emits a warning when the decorated function is called with the deprecated argument.
    If the `scverse_misc` Sphinx extension is enabled,
    the documentation will be modified to include a deprecation notice.

    Args:
        arg: The deprecated argument.
        msg: The deprecation message.
        category: The category of the warning that will be emitted at runtime.
        stacklevel: Override the stack level of the warning. By default it’s the first frame
            outside your package and any wrappers around it, which is right however many
            decorators are stacked on the function.

    Examples:
        >>> @deprecated_arg("bar", Deprecation("0.2", "The functionality has moved to the baz() function."))
        ... def foo(baz, bar=1):
        ...     pass

    .. seealso::
       :ref:`example-deprecating-a-function-argument`
    """

    def __init__(
        self,
        arg: LiteralString,
        msg: Deprecation,
        *,
        category: type[Warning] = FutureWarning,
        stacklevel: int | None = None,
    ) -> None:
        self.arg = arg
        self.msg = msg
        self.category = category
        self.stacklevel = stacklevel
        self.skip_file_prefixes = caller_skip_prefixes(stacklevel=2)

    def __call__[**P, R](self, func: Callable[P, R]) -> CallableWithDeprecatedArg[P, R]:
        warnmsg = f"The argument {self.arg} is deprecated and will be removed in the future."
        if len(self.msg):
            warnmsg += f" {self.msg}"

        sig = inspect.signature(func)
        param = sig.parameters[self.arg]

        def emit() -> None:
            if self.stacklevel is not None:
                warn(warnmsg, category=self.category, stacklevel=self.stacklevel + 2)
            else:  # the walk eats this frame and `wrapped` by itself
                warn_outside(warnmsg, self.category, self.skip_file_prefixes)

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            __tracebackhide__ = True
            if (
                param.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                and self.arg in kwargs
            ):
                emit()
            else:
                bound = sig.bind(*args, **kwargs)
                if self.arg in bound.arguments and bound.arguments[self.arg] != param.default:
                    emit()

            return func(*args, **kwargs)

        args = getattr(func, ATTR_DEPRECATED_ARG, [])
        args.append(self)
        setattr(func, ATTR_DEPRECATED_ARG, args)
        setattr(wrapped, ATTR_DEPRECATED_ARG, args)

        return cast("CallableWithDeprecatedArg[P, R]", wrapped)


class future_abstractmethod:
    """Decorator to indicate that a method will become abstract.

    Until then, the decorated method is the default implementation,
    and defining a concrete subclass that doesn’t override it emits a warning.

    Args:
        msg: The deprecation message.
        category: The category of the warning that will be emitted when a subclass is defined.

    Examples:
        >>> from abc import ABC
        >>> class Base(ABC):
        ...     @future_abstractmethod(Deprecation("0.2", "Implement it to support sparse data."))
        ...     def foo(self):
        ...         raise NotImplementedError  # could also do something
    """

    func: object

    def __init__(self, msg: Deprecation, *, category: type[Warning] = FutureWarning) -> None:
        self.msg = msg
        self.category = category

    def __call__[F](self, func: F) -> F:
        self.func = func
        return cast("F", self)  # replaced by `func` again in `__set_name__`

    def __set_name__(self, owner: type, name: str) -> None:
        setattr(owner, name, self.func)
        warnmsg = "{cls} doesn’t implement {owner}.{name}, which will be required in the future."
        if len(self.msg):
            warnmsg += f" {self.msg}"
        orig = owner.__dict__.get("__init_subclass__")  # already a classmethod

        def __init_subclass__(cls: type, /, **kwargs: object) -> None:
            __tracebackhide__ = True
            if orig is None:
                super(owner, cls).__init_subclass__(**kwargs)  # type: ignore[arg-type]
            else:
                orig.__get__(None, cls)(**kwargs)
            impl_cls = next(c for c in cls.__mro__ if name in c.__dict__)
            if impl_cls is owner and not _is_abstract(cls):
                warn_outside(warnmsg.format(cls=cls.__qualname__, owner=owner.__qualname__, name=name), self.category)

        owner.__init_subclass__ = classmethod(__init_subclass__)  # type: ignore[method-assign,assignment]


def _is_abstract(cls: type) -> bool:
    """Like :func:`inspect.isabstract`, but usable before :class:`abc.ABCMeta` has finished creating `cls`."""
    names = {n for b in cls.__bases__ for n in getattr(b, "__abstractmethods__", ())}
    names |= {n for n, v in cls.__dict__.items() if getattr(v, "__isabstractmethod__", False)}
    return any(getattr(getattr(cls, n, None), "__isabstractmethod__", False) for n in names)
