from __future__ import annotations

import sys
from inspect import getdoc
from typing import TYPE_CHECKING, LiteralString

if sys.version_info >= (3, 13):
    from warnings import deprecated as _deprecated
else:
    from typing_extensions import deprecated as _deprecated

if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["deprecated", "Deprecation"]


class Deprecation(str):
    """Utility class storing information on deprecated functionality.

    Args:
        version_deprecated: The version of the package where the functionality was deprecated.
        msg: The deprecation message.
    """

    version_deprecated: LiteralString

    def __new__(cls, version_deprecated: LiteralString, msg: LiteralString = "") -> LiteralString:  # type: ignore[misc]  # typing.Intersection doesn’t exist yet
        if not msg:
            msg = ""  # be lenient here, people don’t want to see “None” or “False” here
        obj = super().__new__(cls, msg)
        obj.version_deprecated = version_deprecated
        return obj


def _deprecated_at[F: Callable[..., object]](
    msg: Deprecation, *, category: type[Warning] = FutureWarning, stacklevel: int = 1
) -> Callable[[F], F]:
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

        doc = getdoc(func)
        docmsg = f".. version-deprecated:: {msg.version_deprecated}"
        if len(msg):
            docmsg += f"\n   {msg}"
            warnmsg += f" {msg}"

        if doc is None:
            doc = docmsg
        else:
            lines = doc.splitlines()
            body = "\n".join(lines[1:])
            doc = f"{lines[0]}\n\n{docmsg}\n{body}"
        func.__doc__ = doc

        return _deprecated(warnmsg, category=category, stacklevel=stacklevel)(func)

    return decorate


if TYPE_CHECKING:
    deprecated = _deprecated
else:
    deprecated = _deprecated_at
