from __future__ import annotations

import functools
import inspect
import sys
import warnings
from collections.abc import Callable, Mapping
from functools import WRAPPER_ASSIGNMENTS
from types import FunctionType, GenericAlias
from typing import TYPE_CHECKING, ParamSpec, TypedDict, TypeVar, TypeVarTuple, Unpack, cast

if TYPE_CHECKING:
    from types import FrameType

    from pydantic.fields import FieldInfo


class _BaseOverrides(TypedDict, total=False):
    __module__: str
    __name__: str
    __qualname__: str
    __doc__: str | None
    __signature__: inspect.Signature
    __annotations__: Mapping[str, object]
    __type_params__: tuple[TypeVar | TypeVarTuple | ParamSpec, ...]


if sys.version_info >= (3, 14):
    from annotationlib import Format

    class Overrides(_BaseOverrides, total=False):
        __annotate__: Callable[[Format], Mapping[str, object]]
else:

    class Overrides(_BaseOverrides, total=False):
        pass


def copy_func[F: FunctionType](func: F, /, **overrides: Unpack[Overrides]) -> F:
    kw = dict(kwdefaults=func.__kwdefaults__) if sys.version_info >= (3, 13) else {}
    new = FunctionType(
        func.__code__, func.__globals__, name=func.__name__, argdefs=func.__defaults__, closure=func.__closure__, **kw
    )
    for key, value in overrides.items():
        setattr(new, key, value)
    copy = set(WRAPPER_ASSIGNMENTS) - overrides.keys()
    wrapper = functools.update_wrapper(new, func, assigned=copy)
    del wrapper.__wrapped__  # otherwise sphinx will try to document that.
    return cast("F", wrapper)


def package_prefix(mod_name: str) -> str | None:
    """Root directory of `mod_name`’s package, its own file if it isn’t in one, `None` if unimported."""
    if (root := sys.modules.get(mod_name.partition(".")[0])) is not None and (path := getattr(root, "__path__", None)):
        return cast("str", next(iter(path)))
    return cast("str | None", getattr(sys.modules.get(mod_name), "__file__", None))


def caller_skip_prefixes(*, stacklevel: int = 1) -> tuple[str, ...]:
    """Prefixes covering the package of the frame at `stacklevel`, plus our own.

    `stacklevel=1` means the frame calling this function, as in :func:`warnings.warn`.
    """
    caller = sys._getframe(stacklevel).f_globals.get("__name__", "")
    return tuple(p for mod in dict.fromkeys((caller, __package__)) if (p := package_prefix(mod)) is not None)


def _is_wrapper_frame(frame: FrameType, prefixes: tuple[str, ...]) -> bool:
    if frame.f_code.co_filename.startswith(prefixes):
        return True
    # `singledispatch`, `contextmanager`, … – by module name, so frozen `abc` is covered
    # and `site-packages` (below the stdlib dir) isn’t.
    if frame.f_globals.get("__name__", "").partition(".")[0] in sys.stdlib_module_names:
        return True
    return bool(frame.f_locals.get("__tracebackhide__", frame.f_globals.get("__tracebackhide__")))


def warn_outside(
    message: str, category: type[Warning] = UserWarning, prefixes: tuple[str, ...] = (), *, stacklevel: int = 1
) -> None:
    """:func:`warnings.warn`, blaming the first frame that isn’t a wrapper.

    Walks out of `prefixes`, stdlib frames and frames marked `__tracebackhide__`.
    `stacklevel=1` means the caller, as in :func:`warnings.warn`.

    Not `warn(skip_file_prefixes=…)`: before Python 3.14 that only ever skips one frame.
    """
    # `sys._getframe(i)` counts from 0 = here, `warn(stacklevel=s)` from 1 = here.
    frame: FrameType | None = sys._getframe(stacklevel)
    level = stacklevel + 1
    while frame is not None and _is_wrapper_frame(frame, prefixes):
        frame, level = frame.f_back, level + 1
    warnings.warn(message, category, stacklevel=level)


def get_packagename(cls: type | str) -> str:
    package_name = cls.__module__ if not isinstance(cls, str) else cls
    dotidx = package_name.find(".")
    if dotidx > -1:
        package_name = package_name[:dotidx]
    return package_name


def type_str(cls: type, field: FieldInfo) -> str:
    if isinstance(field.annotation, GenericAlias) or not isinstance(field.annotation, type):
        return str(field.annotation)
    if field.annotation.__module__ in {"builtins", cls.__module__}:
        return field.annotation.__qualname__
    return f"{field.annotation.__module__}.{field.annotation.__qualname__}"
