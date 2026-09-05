from contextlib import suppress

from ._arg_alias import arg_alias
from ._deprecated import Deprecation, deprecated, deprecated_arg
from ._extensions import ExtensionNamespace, make_register_namespace_decorator

__all__ = [
    "ExtensionNamespace",
    "make_register_namespace_decorator",
    "deprecated",
    "deprecated_arg",
    "Deprecation",
    "arg_alias",
]

with suppress(ImportError):
    from ._settings import Settings  # noqa: F401

    __all__.append("Settings")
