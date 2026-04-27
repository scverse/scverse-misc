from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from scverse_misc import _extensions as extensions
from scverse_misc import make_register_namespace_decorator

if TYPE_CHECKING:
    from collections.abc import Generator


class Greeter(Protocol):
    def __init__(self, obj: DummyClass) -> None: ...
    def greet(self) -> str: ...


class DummyClass:
    foo: list[object] = []
    bar = None

    @property
    def baz(self) -> None: ...
    def foobar(self) -> None: ...

    dummy: Greeter  # available when using `dummy_namespace` fixture


register_dummy_namespace = make_register_namespace_decorator(DummyClass, "obj", "register_dummy_namespace")


@pytest.fixture
def obj() -> DummyClass:
    """Create a basic object for testing."""
    return DummyClass()


@pytest.fixture(autouse=True)
def _cleanup_dummy() -> Generator[None, None, None]:
    """Automatically cleanup dummy namespace after each test."""
    original = getattr(DummyClass, "dummy", None)
    yield
    if original is not None:
        DummyClass.dummy = original
    elif hasattr(DummyClass, "dummy"):
        delattr(DummyClass, "dummy")


@pytest.fixture
def dummy_namespace() -> type:
    """Create a basic dummy namespace class."""

    @register_dummy_namespace("dummy")
    class DummyNamespace:
        def __init__(self, obj: DummyClass) -> None:
            self._obj = obj

        def greet(self) -> str:
            return "hello"

    return DummyNamespace


def test_accessor_namespace() -> None:
    """Test the behavior of the AccessorNameSpace descriptor.

    This test verifies that:
    - When accessed at the class level (i.e., without an instance), the descriptor
      returns the namespace type.
    - When accessed via an instance, the descriptor instantiates the namespace,
      passing the instance to its constructor.
    - The instantiated namespace is then cached on the instance such that subsequent
      accesses of the same attribute return the cached namespace instance.
    """

    # Define a dummy namespace class to be used via the descriptor.
    class DummyNamespace:
        def __init__(self, obj: Dummy):
            self._obj = obj

        def foo(self) -> str:
            return "foo"

    class Dummy:
        dummy: DummyNamespace  # just typing, runtime added below

    descriptor: extensions.AccessorNameSpace[Dummy, DummyNamespace] = extensions.AccessorNameSpace(
        "dummy", DummyNamespace
    )

    # When accessed on the class, it should return the namespace type.
    ns_class = descriptor.__get__(None, Dummy)
    assert ns_class is DummyNamespace

    # When accessed via an instance, it should instantiate DummyNamespace.
    dummy_obj = Dummy()
    ns_instance = descriptor.__get__(dummy_obj, Dummy)
    assert isinstance(ns_instance, DummyNamespace)
    assert ns_instance._obj is dummy_obj

    # __get__ should cache the namespace instance on the object.
    # Subsequent access should return the same cached instance.
    assert dummy_obj.dummy is ns_instance


def test_descriptor_instance_caching(dummy_namespace: type, obj: DummyClass) -> None:
    """Test that namespace instances are cached on individual DummyClass objects."""
    # First access creates the instance
    ns_instance = obj.dummy
    # Subsequent accesses should return the same instance
    assert obj.dummy is ns_instance


def test_register_namespace_basic(dummy_namespace: type, obj: DummyClass) -> None:
    """Test basic namespace registration and access."""
    assert obj.dummy.greet() == "hello"


def test_register_namespace_override(dummy_namespace: type) -> None:
    """Test namespace registration and override behavior."""
    assert hasattr(DummyClass, "dummy")

    # Override should warn and update the namespace
    with pytest.warns(UserWarning, match="Overriding existing custom namespace 'dummy'"):

        @register_dummy_namespace("dummy")
        class DummyNamespaceOverride:
            def __init__(self, obj: DummyClass) -> None:
                self._obj = obj

            def greet(self) -> str:
                return "world"

    # Verify the override worked
    obj = DummyClass()
    assert obj.dummy.greet() == "world"


@pytest.mark.parametrize(
    "attr",
    [
        "foo",
        "bar",
        "baz",
        "foobar",
    ],
)
def test_register_existing_attributes(attr: str) -> None:
    """
    Test that registering an accessor with a name that is a reserved attribute of DummyClass raises an attribute error.
    """
    with pytest.raises(AttributeError, match=f"cannot override reserved attribute {attr!r}"):

        @register_dummy_namespace(attr)
        class DummyNamespace:
            def __init__(self, obj: DummyClass) -> None:
                self._obj = obj


def test_valid_signature() -> None:
    """Test that a namespace with valid signature is accepted."""

    @register_dummy_namespace("valid")
    class ValidNamespace:
        def __init__(self, obj: DummyClass) -> None:
            self.obj = obj


def test_missing_param() -> None:
    """Test that a namespace missing the second parameter is rejected."""
    with pytest.raises(
        TypeError, match=r"Namespace initializer must accept a DummyClass instance as the second parameter\."
    ):

        @register_dummy_namespace("missing_param")
        class MissingParamNamespace:
            def __init__(self) -> None:
                pass


def test_wrong_name() -> None:
    """Test that a namespace with wrong parameter name is rejected."""
    with pytest.raises(
        TypeError, match=r"Namespace initializer's second parameter must be named 'obj', got 'notobj'\."
    ):

        @register_dummy_namespace("wrong_name")
        class WrongNameNamespace:
            def __init__(self, notobj: DummyClass) -> None:
                self.notobj = notobj


def test_wrong_annotation() -> None:
    """Test that a namespace with wrong parameter annotation is rejected."""
    with pytest.raises(
        TypeError,
        match=r"Namespace initializer's second parameter must be annotated as the 'DummyClass' class, got 'int'\.",
    ):

        @register_dummy_namespace("wrong_annotation")
        class WrongAnnotationNamespace:
            def __init__(self, obj: int) -> None:
                self.obj = obj


def test_missing_annotation() -> None:
    """Test that a namespace with missing parameter annotation is rejected."""
    with pytest.raises(AttributeError):

        @register_dummy_namespace("missing_annotation")
        class MissingAnnotationNamespace:
            def __init__(self, obj: object) -> None:
                self.obj = obj


def test_both_wrong() -> None:
    """Test that a namespace with both wrong name and annotation is rejected."""
    with pytest.raises(
        TypeError,
        match=(
            r"Namespace initializer's second parameter must be named 'obj', got 'info'\. "
            r"And must be annotated as 'DummyClass', got 'str'\."
        ),
    ):

        @register_dummy_namespace("both_wrong")
        class BothWrongNamespace:
            def __init__(self, info: str) -> None:
                self.info = info
