import functools
import sys
from functools import WRAPPER_ASSIGNMENTS
from types import FunctionType
from typing import ParamSpec, TypedDict, TypeVar, TypeVarTuple, Unpack, cast


class Overrides(TypedDict, total=False):
    __module__: str
    __name__: str
    __qualname__: str
    __doc__: str
    # ≥3.14: __annotate__, <3.14: __annotations__
    __type_params__: tuple[TypeVar | TypeVarTuple | ParamSpec, ...]


def copy_func[F: FunctionType](func: F, /, **overrides: Unpack[Overrides]) -> F:
    kw = dict(kwdefaults=func.__kwdefaults__) if sys.version_info >= (3, 13) else {}
    new = FunctionType(
        func.__code__, func.__globals__, name=func.__name__, argdefs=func.__defaults__, closure=func.__closure__, **kw
    )
    for key, value in overrides.items():
        setattr(new, key, value)
    copy = set(WRAPPER_ASSIGNMENTS) - overrides.keys()
    return cast("F", functools.update_wrapper(new, func, assigned=copy))
