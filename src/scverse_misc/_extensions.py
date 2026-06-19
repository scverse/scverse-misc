"""System to add extension attributes to classes.

Based off of the extension framework in Polars:
https://github.com/pola-rs/polars/blob/main/py-polars/polars/api.py
"""

from __future__ import annotations

import inspect
import sys
import warnings
from itertools import islice
from typing import TYPE_CHECKING, NamedTuple, Protocol, get_type_hints, overload, runtime_checkable

from .constants import ATTR_NAMESPACE

if TYPE_CHECKING:
    from collections.abc import Callable, Set


__all__ = ["make_register_namespace_decorator", "ExtensionNamespace"]


@runtime_checkable
class ExtensionNamespace(Protocol):
    """Protocol for extension namespaces.

    Enforces that the namespace initializer accepts a class with the proper `__init__` method.
    Protocol's can't enforce that the `__init__` accepts the correct types. See
    `_check_namespace_signature` for that. This is mainly useful for static type
    checking with mypy and IDEs.
    """

    def __init__(self, instance: object) -> None:
        """Used to enforce the correct signature for extension namespaces."""


class AccessorNameSpace[T, NameSpT: ExtensionNamespace]:
    """Establish property-like namespace object for user-defined functionality."""

    def __init__(self, name: str, namespace: type[NameSpT]) -> None:
        self._accessor = name
        self._ns = namespace

    @overload
    def __get__(self, instance: None, cls: type[T]) -> type[NameSpT]: ...

    @overload
    def __get__(self, instance: T, cls: type[T]) -> NameSpT: ...

    def __get__(self, instance: T | None, cls: type[T]) -> NameSpT | type[NameSpT]:
        if instance is None:
            return self._ns

        ns_instance = self._ns(instance)
        setattr(instance, self._accessor, ns_instance)
        return ns_instance


def _check_namespace_signature(ns_class: type, cls: type, canonical_instance_name: str) -> None:
    """Validate the signature of a namespace class for extensions.

    This function ensures that any class intended to be used as an extension namespace
    has a properly formatted `__init__` method such that:

    1. Accepts at least two parameters (self and the instance of the extended class)
    2. Has `canonical_instance_name` as the name of the second parameter
    3. Has the second parameter properly type-annotated as `ns_class` or any equivalent import alias

    The function performs runtime validation of these requirements before a namespace
    can be registered through the `register_namespace` decorator.

    Args:
        ns_class: The namespace class to validate.
        cls: The class that is being extended.
        canonical_instance_name: The name of the `ns_class` constructor argument.

    Raises:
        TypeError: If the `__init__` method has fewer than 2 parameters (missing the instance parameter).
        AttributeError: If the second parameter of `__init__` lacks a type annotation.
        TypeError: If the second parameter of `__init__` is not named `canonical_instance_name`.
        TypeError: If the second parameter of `__init__` is not annotated as the `ns_class` class.
        TypeError: If both the name and type annotation of the second parameter are incorrect.

    """
    sig = inspect.signature(ns_class.__init__)  # type: ignore[misc]  # https://github.com/python/mypy/issues/21236
    params = sig.parameters

    # Ensure there are at least two parameters (self and mdata)
    if len(params) < 2:
        raise TypeError(f"Namespace initializer must accept a {cls.__name__} instance as the second parameter.")

    # Get the second parameter (expected to be `canonical_instance_name`)
    [_, param, *_] = params.values()
    if param.annotation is inspect.Parameter.empty:
        raise AttributeError(
            f"Namespace initializer's second parameter must be annotated as the {cls.__name__!r} class, got empty annotation."
        )

    name_ok = param.name == canonical_instance_name

    # Resolve the annotation using get_type_hints to handle forward references and aliases.
    try:
        type_hints = get_type_hints(ns_class.__init__)  # type: ignore[misc]  # https://github.com/python/mypy/issues/21236
        resolved_type = type_hints.get(param.name, param.annotation)
    except NameError as e:
        raise NameError(
            f"Namespace initializer's second parameter must be named {canonical_instance_name!r}, got '{param.name}'."
        ) from e

    type_ok = resolved_type is cls

    match (name_ok, type_ok):
        case (True, True):
            return  # Signature is correct.
        case (False, True):
            raise TypeError(
                f"Namespace initializer's second parameter must be named {canonical_instance_name!r}, got {param.name!r}."
            )
        case (True, False):
            type_repr = getattr(resolved_type, "__name__", str(resolved_type))
            raise TypeError(
                f"Namespace initializer's second parameter must be annotated as the {cls.__name__!r} class, got {type_repr!r}."
            )
        case _:
            type_repr = getattr(resolved_type, "__name__", str(resolved_type))
            raise TypeError(
                f"Namespace initializer's second parameter must be named {canonical_instance_name!r}, got {param.name!r}. "
                f"And must be annotated as {cls.__name__!r}, got {type_repr!r}."
            )


def _create_namespace[NameSpT: ExtensionNamespace](
    name: str, cls: type, reserved_namespaces: Set[str], canonical_instance_name: str
) -> Callable[[type[NameSpT]], type[NameSpT]]:
    """Register custom namespace against the underlying class."""

    def namespace(ns_class: type[NameSpT]) -> type[NameSpT]:
        _check_namespace_signature(ns_class, cls, canonical_instance_name)  # Perform the runtime signature check
        if name in reserved_namespaces:
            raise AttributeError(f"cannot override reserved attribute {name!r}")
        elif hasattr(cls, name):
            warnings.warn(
                f"Overriding existing custom namespace {name!r} (on {cls.__name__!r})", UserWarning, stacklevel=2
            )
        setattr(cls, name, AccessorNameSpace(name, ns_class))
        return ns_class

    return namespace


def _indent_string_lines(string: str, indentation_level: int, skip_lines: int = 0) -> str:
    minspace = sys.maxsize
    for line in islice(string.splitlines(), 1, None):
        for i, char in enumerate(line):
            if not char.isspace():
                minspace = min(minspace, i)
                break
    if minspace == sys.maxsize:  # single-line string
        minspace = 0
    return "\n".join(
        " " * 4 * indentation_level + sline if i >= skip_lines else sline
        for i, line in enumerate(string.splitlines())
        if (sline := (line[minspace:] if i > 0 else line)) or True
    )


class _NSInfo(NamedTuple):
    name: str
    """Canonical instance name."""

    cls: type
    """Namespace Class."""


def make_register_namespace_decorator[NameSpT: ExtensionNamespace](
    cls: type, canonical_instance_name: str, decorator_name: str | None = None, docstring_style: str | None = None
) -> Callable[[str], Callable[[type[NameSpT]], type[NameSpT]]]:
    """Create a decorator for registering custom functionality with a class.

    The decorator will allow your users to extend `cls` objects with custom methods and properties
    organized under a namespace. The namespace becomes accessible as an attribute on `cls` instances,
    providing a clean way for users to add domain-specific functionality without modifying the `cls`
    class itself.

    If the `scverse_misc` Sphinx extension is enabled, the returned decorator will be documented along with examples.

    Args:
        cls: The class to be made extensible.
        canonical_instance_name: The typical name of an instance of `cls`, e.g. `adata` for `AnnData`. This
            is used for run-time checking of constructor signatures of the namespace classes.
        decorator_name: Deprecated and unused.
        docstring_style: Deprecated and unused.
    """
    if decorator_name is not None:
        warnings.warn(
            "The decorator_name argument is deprecated and will be removed in the future.",
            category=DeprecationWarning,
            stacklevel=2,
        )
    if docstring_style is not None:
        warnings.warn(
            "The docstring_style argument is deprecated and will be removed in the future.",
            category=DeprecationWarning,
            stacklevel=2,
        )
    # Reserved namespaces include accessors built into cls and all current attributes of cls
    reserved_namespaces = set(dir(cls))

    def decorator(name: str) -> Callable[[type[NameSpT]], type[NameSpT]]:
        return _create_namespace(name, cls, reserved_namespaces, canonical_instance_name)

    setattr(decorator, ATTR_NAMESPACE, _NSInfo(canonical_instance_name, cls))

    return decorator
