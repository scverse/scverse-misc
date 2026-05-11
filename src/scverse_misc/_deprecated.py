from __future__ import annotations

import inspect
import sys
from contextlib import suppress
from functools import wraps
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
        if len(msg):
            warnmsg += f" {msg}"

        if func.__doc__ is not None:
            with suppress(ImportError):
                func.__doc__ = _deprecate_arg_doc(func.__doc__, arg=arg, msg=msg)

        sig = inspect.signature(func)
        param = sig.parameters[arg]

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            if (
                param.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                and arg in kwargs
            ):
                warn(warnmsg, category=category, stacklevel=stacklevel + 1)
            else:
                bound = sig.bind(*args, **kwargs)
                if arg in bound.arguments and bound.arguments[arg] != param.default:
                    warn(warnmsg, category=category, stacklevel=stacklevel + 1)

            return func(*args, **kwargs)

        return wrapped

    return decorate


def _deprecate_arg_doc(doc: str, *, arg: str, msg: Deprecation) -> str:
    from pydocstring import Docstring, Section, SectionKind, Style, emit_google, emit_numpy, parse

    docmsg = f".. version-deprecated:: {msg.version_deprecated}"
    if len(msg):
        docmsg += f"\n   {msg}"

    parsed = parse(doc)
    if parsed.style is Style.PLAIN:
        return doc

    model = parsed.to_model()
    with suppress(StopIteration):
        for s, section in enumerate(model.sections):
            if section.kind not in {
                SectionKind.PARAMETERS,
                SectionKind.KEYWORD_PARAMETERS,
                SectionKind.OTHER_PARAMETERS,
            }:
                continue
            for p, par in enumerate(section.parameters):
                if arg not in par.names:
                    continue
                if par.description is not None:
                    docmsg += f"\n\n{par.description}"
                par.description = docmsg
                params = list(section.parameters)
                params[p] = par
                sections = list(model.sections)
                sections[s] = Section(section.kind, parameters=params)
                model = Docstring(
                    summary=model.summary,
                    extended_summary=model.extended_summary,
                    deprecation=model.deprecation,
                    sections=sections,
                )
                raise StopIteration
    match parsed.style:
        case Style.GOOGLE:
            return emit_google(model)
        case Style.NUMPY:
            return emit_numpy(model)
        case _:  # pragma: no cover
            raise AssertionError
