from __future__ import annotations

import sys
from contextlib import suppress
from typing import TYPE_CHECKING, LiteralString, TypeVar

if sys.version_info >= (3, 13):
    from warnings import deprecated as _deprecated
else:
    from typing_extensions import deprecated as _deprecated

if TYPE_CHECKING:
    from collections.abc import Callable

    F = TypeVar("F", bound=Callable)


class Deprecation(str):
    """Utility class storing information on deprecated functionality.

    Args:
        version_deprecated: The version of the package where the functionality was deprecated.
        msg: The deprecation message.
    """

    def __new__(cls, version_deprecated: LiteralString, msg: LiteralString = "") -> LiteralString:
        obj = super().__new__(cls, msg)
        obj.version_deprecated = version_deprecated
        return obj


def _deprecated_at(msg: Deprecation, *, category=FutureWarning, stacklevel=1) -> Callable[[F], F]:
    """Decorator to indicate that a class, function, or overload is deprecated.

    Wraps :func:`warnings.deprecated` and additionally modifies the docstring to include a deprecation notice.

    Args:
        msg: The deprecation message.
        category: The category of the warning that will be emitted at runtime.
        stacklevel: The stack level of the warning.

    Examples:
        >>> @deprecated(Deprecation("0.2", "Use bar() instead."))
        ... def foo(baz):
        ...     pass
    """

    def decorate(func: F) -> F:
        kind = "function" if func.__name__ == func.__qualname__ else "method"
        warnmsg = f"The {kind} {func.__name__} is deprecated and will be removed in the future."

        doc = func.__doc__
        indentation = ""
        if doc is not None:
            lines = doc.expandtabs().splitlines()
            with suppress(StopIteration):
                for line in lines[1:]:
                    if not len(line):
                        continue
                    for indentation, char in enumerate(line):
                        if not char.isspace():
                            indentation = line[:indentation]
                            raise StopIteration  # break out of both loops

        docmsg = f"{indentation}.. version-deprecated:: {msg.version_deprecated}"
        if len(msg) is not None:
            docmsg += f"\n{indentation}   {msg}"
            warnmsg += f" {msg}"

        if doc is None:
            doc = docmsg
        else:
            body = "\n".join(lines[1:])
            doc = f"{lines[0]}\n\n{docmsg}\n{body}"
        func.__doc__ = doc

        return _deprecated(warnmsg, category=category, stacklevel=stacklevel)(func)

    return decorate


if TYPE_CHECKING:
    deprecated = _deprecated
else:
    deprecated = _deprecated_at
