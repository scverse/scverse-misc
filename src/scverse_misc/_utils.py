from __future__ import annotations

import functools
import inspect
import sys
from collections.abc import Callable, Mapping
from functools import WRAPPER_ASSIGNMENTS
from pathlib import Path
from types import FunctionType, GenericAlias
from typing import TYPE_CHECKING, ParamSpec, TypedDict, TypeVar, TypeVarTuple, Unpack, cast

if TYPE_CHECKING:
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


def get_packagename(cls: type | str) -> str:
    package_name = cls.__module__ if not isinstance(cls, str) else cls
    dotidx = package_name.find(".")
    if dotidx > -1:
        package_name = package_name[:dotidx]
    return package_name


def get_caller_package(stacklevel: int = 0) -> str | None:
    frame = inspect.currentframe()
    if TYPE_CHECKING:
        assert frame is not None
    for _ in range(stacklevel + 2):
        if (back := frame.f_back) is not None:
            frame = back
        else:
            break
    module = inspect.getmodule(frame)
    return get_packagename(module.__name__) if module is not None else None


def get_package_file_prefixes(packagename: str) -> tuple[str, ...]:
    try:
        module = sys.modules[packagename]
    except KeyError:
        return ()
    if file := module.__file__:
        return (str(Path(file).parent),)
    else:  # namespace package
        if (spec := module.__spec__) is not None and (locs := spec.submodule_search_locations) is not None:
            return tuple(locs)
        else:
            return ()


def get_caller_package_file_prefixes() -> tuple[str, ...]:
    caller_pkg = get_caller_package(1)
    return get_package_file_prefixes(caller_pkg) if caller_pkg is not None else ()


def type_str(cls: type, field: FieldInfo) -> str:
    if isinstance(field.annotation, GenericAlias) or not isinstance(field.annotation, type):
        return str(field.annotation)
    if field.annotation.__module__ in {"builtins", cls.__module__}:
        return field.annotation.__qualname__
    return f"{field.annotation.__module__}.{field.annotation.__qualname__}"
