"""System to add extension attributes to classes.

Based off of the extension framework in Polars:
https://github.com/pola-rs/polars/blob/main/py-polars/polars/api.py
"""

from __future__ import annotations

import inspect
import sys
import warnings
from itertools import islice
from typing import TYPE_CHECKING, Literal, Protocol, get_type_hints, overload, runtime_checkable

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


def make_register_namespace_decorator[NameSpT: ExtensionNamespace](
    cls: type, canonical_instance_name: str, decorator_name: str, docstring_style: Literal["google", "numpy"] = "google"
) -> Callable[[str], Callable[[type[NameSpT]], type[NameSpT]]]:
    """Create a decorator for registering custom functionality with a class.

    The decorator will allow your users to extend `cls` objects with custom methods and properties
    organized under a namespace. The namespace becomes accessible as an attribute on `cls` instances,
    providing a clean way for users to add domain-specific functionality without modifying the `cls`
    class itself.

    The return decorator will have a docstring describing how to use it along with examples.

    Args:
        cls: The class to be made extensible.
        canonical_instance_name: The typical name of an instance of `cls`, e.g. `adata` for `AnnData`. This
            is used for run-time checking of constructor signatures of the namespace classes.
        decorator_name: The name under which the decorator is accessible in your package. This is used for
            the examples in the decorator docstring.
        docstring_style: Whether the docstring of the generated decorator should conform to NumPy or Google
            style.
    """
    # Reserved namespaces include accessors built into cls and all current attributes of cls
    reserved_namespaces = set(dir(cls))

    def decorator(name: str) -> Callable[[type[NameSpT]], type[NameSpT]]:
        return _create_namespace(name, cls, reserved_namespaces, canonical_instance_name)

    decorator_arg_description = f"""Name under which the accessor should be registered. This will be the attribute name
            used to access your namespace's functionality on {cls.__name__} objects (e.g., `instance.name`).
            Cannot conflict with existing {cls.__name__} attributes. The list of reserved attributes includes
            everything outputted by `dir({cls.__name__})`."""
    decorator_return_description = "A decorator that registers the decorated class as a custom namespace."
    decorator_notes = f"""Implementation requirements:

        1. The decorated class must have an `__init__` method that accepts exactly one parameter
           (besides `self`) named `{canonical_instance_name}` and annotated with type :class:`~{cls.__module__}.{cls.__name__}`.
        2. The namespace will be initialized with the {cls.__name__} object on first access and then
           cached on the instance.
        3. If the namespace name conflicts with an existing namespace, a warning is issued.
        4. If the namespace name conflicts with a built-in {cls.__name__} attribute, an AttributeError is raised."""
    decorator_examples = f""">>> @{decorator_name}("do_something")
        ... class DoSomething:
        ...     def __init__(self, {canonical_instance_name}: {cls.__name__}):
        ...         self._obj = {canonical_instance_name}
        ...
        ...     def has_foo(self) -> bool:
        ...         return hasattr(self._obj, "foo")
        >>>
        >>> # Create a {cls.__name__} object
        >>> obj = {cls.__name__}()
        >>>
        >>> # use the registered namespace
        >>> obj.do_something.has_foo()
        False"""

    decorator.__doc__ = f"""Decorator for registering custom functionality with a :class:`~{cls.__module__}.{cls.__name__}` object.

    This decorator allows you to extend {cls.__name__} objects with custom methods and properties
    organized under a namespace. The namespace becomes accessible as an attribute on {cls.__name__}
    instances, providing a clean way to you to add domain-specific functionality without modifying
    the {cls.__name__} class itself, or extending the class with additional methods as you see fit in your workflow.
    """

    if docstring_style == "google":
        decorator.__doc__ += f"""
    Args:
        name: {_indent_string_lines(decorator_arg_description, 3, 1)}

    Returns:
        {_indent_string_lines(decorator_return_description, 2, 1)}

    Notes:
        {_indent_string_lines(decorator_notes, 2, 1)}

    Examples:
        {_indent_string_lines(decorator_examples, 2, 1)}
    """
    else:
        decorator.__doc__ += f"""
    Parameters
    ----------
    name
        {_indent_string_lines(decorator_arg_description, 2, 1)}

    Returns
    -------
    {_indent_string_lines(decorator_return_description, 1, 1)}

    Notes
    -----
    {_indent_string_lines(decorator_notes, 1, 1)}

    Examples
    --------
    {_indent_string_lines(decorator_examples, 1, 1)}
    """

    return decorator
