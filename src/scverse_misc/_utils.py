import functools
import sys
from collections.abc import Callable, Mapping
from functools import WRAPPER_ASSIGNMENTS
from types import FunctionType
from typing import ParamSpec, TypedDict, TypeVar, TypeVarTuple, Unpack, cast


class _BaseOverrides(TypedDict, total=False):
    __module__: str
    __name__: str
    __qualname__: str
    __doc__: str
    __type_params__: tuple[TypeVar | TypeVarTuple | ParamSpec, ...]


if sys.version_info >= (3, 14):
    from annotationlib import Format

    class Overrides(_BaseOverrides, total=False):
        __annotate__: Callable[[Format], Mapping[str, object]]
else:

    class Overrides(_BaseOverrides, total=False):
        __annotations__: Mapping[str, object]


def copy_func[F: FunctionType](func: F, /, **overrides: Unpack[Overrides]) -> F:
    kw = dict(kwdefaults=func.__kwdefaults__) if sys.version_info >= (3, 13) else {}
    new = FunctionType(
        func.__code__, func.__globals__, name=func.__name__, argdefs=func.__defaults__, closure=func.__closure__, **kw
    )
    for key, value in overrides.items():
        setattr(new, key, value)
    copy = set(WRAPPER_ASSIGNMENTS) - overrides.keys()
    return cast("F", functools.update_wrapper(new, func, assigned=copy))
