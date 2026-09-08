import sys
import typing
from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from inspect import signature
from typing import Any, ForwardRef, Literal, Union, get_args, get_origin, get_type_hints

if sys.version_info >= (3, 14):
    from typing import evaluate_forward_ref

    from annotationlib import Format, get_annotations
else:
    from typing_extensions import Format, evaluate_forward_ref, get_annotations


def _compute_aliases(func: Callable[..., Any], argname: str) -> tuple[dict[object, object], set[object]]:
    try:
        hint = get_type_hints(func)[argname]
    except NameError:
        hint = get_annotations(func, format=Format.FORWARDREF)[argname]
        if isinstance(hint, ForwardRef):
            hint = evaluate_forward_ref(hint)
        elif isinstance(hint, str):
            globalns = {}
            try:
                globalns = func.__globals__
            except AttributeError:  # possibly a class
                with suppress(AttributeError, KeyError):
                    globalns = sys.modules[func.__module__].__dict__
            globalns.update({"typing": typing, "Literal": Literal, "Union": Union})
            hint = eval(hint, globalns)

    if get_origin(hint) is Literal:
        sets = (hint,)
    elif get_origin(hint) is Union:
        sets = get_args(hint)
    else:
        msg = f"Type hint for argument {argname!r} must be 'Union' or 'Literal', found {hint!r}."
        raise TypeError(msg)

    replacements: dict[object, object] = {}
    values = set()

    for aliasset in sets:
        if get_origin(aliasset) is not Literal:
            msg = f"All type hints specifying aliases for argument {argname!r} must be 'Literal', found {aliasset!r}."
            raise TypeError(msg)
        value, *aliases = get_args(aliasset)
        if isinstance(value, ForwardRef):
            value = evaluate_forward_ref(value)
        values.add(value)
        replacements.update(
            (evaluate_forward_ref(alias) if isinstance(alias, ForwardRef) else alias, value) for alias in aliases
        )

    return replacements, values


def arg_alias[**P, R](argname: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to specify aliases for function arguments that accept a fixed set of values.

    If a function argument accepts a fixed set of values that partitions into multiple equivalence classes
    (i.e. several values are aliased to the same behavior), this decorator converts each equivalence class
    into its chosen canonical representation before passing it on to the function. This eliminates the need
    for the function to perform validation and conversion itself, the function can be certain that it always
    gets the canonical representation.

    The rules are encoded in the type hint for the aliased argument. If there is only a single set of aliases,
    the type hint must be a :obj:`~typing.Literal` with the canonical representation as first argument followed
    by its aliases. If there are multiple sets of aliases, that is multiple semantically different values that
    the function accepts, the type hint must be a :obj:`~typing.Union` of :obj:`~typing.Literal` s, where each
    :obj:`~typing.Literal` follows the same rules as above: The canonical representation is the first argument
    followed by its aliases.

    Args:
        argname: The name of the argument to alias.

    Examples:
        >>> @axis_arg("axis")
        ... def foo(x: int, axis: Literal[0, "obs"]):
        ...     return axis
        ...
        ...
        ... assert foo(42, 0) == foo(42, "obs") == 0

        >>> @axis_arg("axis")
        ... def foo(x: float, axis: Literal[0, "obs"] | Literal[1, "var", "vars"]):
        ...     return axis
        ...
        ...
        ... assert foo(42, 0) == foo(42, "obs") == 1
        ... assert foo(42, 1) == foo(42, "var") == foo(42, "vars") == 1
    """

    def wrapper(func: Callable[P, R]) -> Callable[P, R]:
        try:
            replacements, values = _compute_aliases(func, argname)
        except NameError:
            replacements, values = None, None  # method has a type hint with its class

        sig = signature(func)

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal replacements, values
            if replacements is None or values is None:
                replacements, values = _compute_aliases(func, argname)

            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            argval = bound.arguments[argname]
            try:
                bound.arguments[argname] = replacements[argval]
            except KeyError:
                if argval not in values:
                    msg = f"Argument {argname!r} must be one of {tuple(values) + tuple(replacements.keys())}, got {argval!r}."
                    raise ValueError(msg) from None
            return func(*bound.args, **bound.kwargs)

        return wrapped

    return wrapper
