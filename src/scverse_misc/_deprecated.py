from __future__ import annotations

import inspect
import sys
from functools import wraps
from textwrap import indent
from textwrap import indent
from typing import TYPE_CHECKING, LiteralString
from warnings import warn

if sys.version_info >= (3, 13):
    from warnings import deprecated as _deprecated
else:
    from typing_extensions import deprecated as _deprecated

if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["deprecated", "deprecated_arg", "Deprecation"]


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
        warnmsg = f"The {kind} {func.__name__} is deprecated and will be removed in the future"

        doc = inspect.getdoc(func)
        docmsg = f".. version-deprecated:: {msg.version_deprecated}"
        if len(msg):
            docmsg += f"\n{indent(msg, 3 * ' ')}"
            warnmsg += f". {msg}" if msg.count("\n") == 0 else f":\n{indent(msg, 4 * ' ')}"
        else:
            warnmsg += "."

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


def deprecated_arg[**P, R](
    arg: LiteralString, msg: Deprecation, *, category: type[Warning] = FutureWarning, stacklevel: int = 1
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to indicate that a function argument is deprecated.

    Emits a warning when the decorated function is called with the deprecated argument and addtionally modifies the
    docstring to include a deprecation notice.

    Args:
        arg: The deprecated argument.
        msg: The deprecation message.
        category: The category of the warning that will be emitted at runtime.
        stacklevel: The stack level of the warning.

    Examples:
        >>> @deprecated_arg("bar", Deprecation("0.2", "The functionality has moved to the baz() function."))
        ... def foo(baz, bar=1):
        ...     pass
    """

    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        warnmsg = f"The argument {arg} is deprecated and will be removed in the future."
        doc = inspect.getdoc(func)
        docmsg = f"    .. version-deprecated:: {msg.version_deprecated}"

        if len(msg):
            docmsg += f"\n       {msg}"
            warnmsg += f" {msg}"

        if doc is not None:
            lines = doc.splitlines()
            docstring_style = None
            in_arg_section = False
            in_arg_header = False
            for i, line in enumerate(lines):
                if in_arg_header:
                    in_arg_header = False
                    continue
                elif not in_arg_section and line == "Parameters" and lines[i + 1] == "----------":
                    docstring_style = "numpy"
                    in_arg_section = True
                    in_arg_header = True
                elif not in_arg_section and line == "Args:":
                    docstring_style = "google"
                    in_arg_section = True
                    docmsg = indent(docmsg, "    ")
                elif in_arg_section:
                    if docstring_style == "numpy" and line == arg:
                        doc = "\n".join(lines[: i + 1]) + f"\n{docmsg}\n\n" + "\n".join(lines[i + 1 :])
                        break
                    elif docstring_style == "google" and line.startswith(prefix := f"    {arg}: "):
                        doc = (
                            "\n".join(lines[:i])
                            + f"\n{prefix}\n{docmsg}\n\n        {line[len(prefix) :]}\n"
                            + "\n".join(lines[i + 1 :])
                        )
                        break
                    elif (
                        docstring_style == "numpy"
                        and set(line.strip()) == {"-"}
                        or docstring_style == "google"
                        and not line[0].isspace()
                    ):  # next section, arg not documented
                        break
            func.__doc__ = doc

        sig = inspect.signature(func)
        param = sig.parameters[arg]

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            if (
                param.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                and arg in kwargs
            ):
                warn(warnmsg, category=category, stacklevel=stacklevel)
            else:
                bound = sig.bind(*args, **kwargs)
                if arg in bound.arguments and bound.arguments[arg] != param.default:
                    warn(warnmsg, category=category, stacklevel=stacklevel)

            return func(*args, **kwargs)

        return wrapped

    return decorate
