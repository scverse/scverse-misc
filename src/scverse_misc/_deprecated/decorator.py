from __future__ import annotations

import sys
from textwrap import indent
from typing import TYPE_CHECKING, LiteralString, cast

if sys.version_info >= (3, 13):
    from warnings import deprecated as _deprecated
else:
    from typing_extensions import deprecated as _deprecated

if TYPE_CHECKING:
    from types import FunctionType

    from scverse_misc import Deprecation

__all__ = ["deprecated", "_deprecated"]


class deprecated(_deprecated):
    """Decorator to indicate that a class, function, or overload is deprecated.

    Wraps :func:`warnings.deprecated`. If the scverse_misc Sphinx extension is enabled, the function's documentation will
    include a deprecation notice.

    Args:
        msg: The deprecation message.
        category: The category of the warning that will be emitted at runtime.
        stacklevel: The stack level of the warning.

    Examples:
        >>> @deprecated(Deprecation("0.2", "Use bar() instead."))
        ... def foo(baz):
        ...     pass

    .. seealso::
       :ref:`example-deprecating-a-function`, :ref:`example-settings-class`
    """

    message: Deprecation

    def __init__(self, msg: Deprecation, *, category: type[Warning] = FutureWarning, stacklevel: int = 1) -> None:
        super().__init__(cast("LiteralString", msg), category=category, stacklevel=stacklevel)

    def __call__[F](self, func: F) -> F:
        from . import Deprecation

        if TYPE_CHECKING:
            assert isinstance(func, FunctionType)
        kind = "function" if func.__name__ == func.__qualname__ else "method"
        warnmsg = f"The {kind} {func.__name__} is deprecated and will be removed in the future"
        if len(self.message):
            warnmsg += f". {self.message}" if self.message.count("\n") == 0 else f":\n{indent(self.message, 4 * ' ')}"
        else:
            warnmsg += "."
        newmsg = Deprecation(self.message.version_deprecated, warnmsg)
        newmsg._docmsg = str(self.message)
        self.message = newmsg
        return super().__call__(func)
