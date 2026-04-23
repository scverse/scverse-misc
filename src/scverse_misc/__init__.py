from contextlib import suppress

from ._deprecated import Deprecation, deprecated
from ._extensions import ExtensionNamespace, make_register_namespace_decorator

__all__ = ["ExtensionNamespace", "make_register_namespace_decorator", "deprecated", "Deprecation"]

with suppress(ImportError):
    from ._settings import Settings

    __all__.append("Settings")
