from __future__ import annotations

import inspect
from functools import wraps
from typing import TYPE_CHECKING, LiteralString, Protocol, cast
from warnings import warn

from ..constants import ATTR_DEPRECATED_ARG

if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["deprecated", "deprecated_arg", "Deprecation"]


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

    def __new__(cls, version_deprecated: LiteralString, msg: LiteralString = "") -> LiteralString:  # type: ignore[misc]  # typing.Intersection doesn’t exist yet
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
        stacklevel: The stack level of the warning.

    Examples:
        >>> @deprecated_arg("bar", Deprecation("0.2", "The functionality has moved to the baz() function."))
        ... def foo(baz, bar=1):
        ...     pass

    .. seealso::
       :ref:`example-deprecating-a-function-argument`
    """

    def __init__(
        self, arg: LiteralString, msg: Deprecation, *, category: type[Warning] = FutureWarning, stacklevel: int = 1
    ) -> None:
        self.arg = arg
        self.msg = msg
        self.category = category
        self.stacklevel = stacklevel

    def __call__[**P, R](self, func: Callable[P, R]) -> CallableWithDeprecatedArg[P, R]:
        warnmsg = f"The argument {self.arg} is deprecated and will be removed in the future."
        if len(self.msg):
            warnmsg += f" {self.msg}"

        sig = inspect.signature(func)
        param = sig.parameters[self.arg]

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            if (
                param.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                and self.arg in kwargs
            ):
                warn(warnmsg, category=self.category, stacklevel=self.stacklevel + 1)
            else:
                bound = sig.bind(*args, **kwargs)
                if self.arg in bound.arguments and bound.arguments[self.arg] != param.default:
                    warn(warnmsg, category=self.category, stacklevel=self.stacklevel + 1)

            return func(*args, **kwargs)

        args = getattr(func, ATTR_DEPRECATED_ARG, [])
        args.append(self)
        setattr(func, ATTR_DEPRECATED_ARG, args)
        setattr(wrapped, ATTR_DEPRECATED_ARG, args)

        return cast(CallableWithDeprecatedArg[P, R], wrapped)
