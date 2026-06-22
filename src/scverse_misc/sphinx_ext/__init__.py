from __future__ import annotations

import sys
import textwrap
import warnings
from importlib.metadata import version
from textwrap import indent
from types import MethodType
from typing import TYPE_CHECKING, cast

if sys.version_info >= (3, 13):
    from warnings import deprecated as deprecated
else:
    from typing_extensions import deprecated as deprecated

from pydocstring import Docstring, Parameter, Return, Section, SectionKind, Style, emit_google, emit_numpy, parse

from .._deprecated import Deprecation, deprecated_arg
from .._extensions import _NSInfo
from .._utils import get_packagename, type_str
from ..constants import ATTR_DEPRECATED, ATTR_DEPRECATED_ARG, ATTR_NAMESPACE

try:
    from pydantic_core import PydanticUndefined

    from .._settings import Settings
except ImportError:
    if not TYPE_CHECKING:
        Settings = type("Settings", (), {})


if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.ext.autodoc import Options as AutodocOptions
    from sphinx.ext.autodoc import _AutodocObjType  # type: ignore[attr-defined]
    from sphinx.util.typing import ExtensionMetadata


__all__ = ["setup"]


def setup(app: Sphinx) -> ExtensionMetadata:  # noqa: D103
    app.setup_extension("sphinx.ext.autodoc")
    # To go first, we use a lower number than napoleon (which uses the default, 500)
    app.connect("autodoc-process-docstring", _process_docstring, priority=100)

    return {"version": version("scverse-misc"), "parallel_read_safe": True}


def _process_docstring(
    app: Sphinx, objtype: _AutodocObjType, name: str, obj: object, options: AutodocOptions, lines: list[str]
) -> None:
    match objtype:
        case "function" | "decorator" if hasattr(obj, ATTR_NAMESPACE):
            assert isinstance(getattr(obj, ATTR_NAMESPACE), _NSInfo)
            _process_namespace_decorator(app, name, getattr(obj, ATTR_NAMESPACE), lines)
        case "method" | "function" if isinstance(obj, MethodType) and isinstance(obj.__self__, Settings):
            _process_settings_method(app, obj, lines)
        case "method" | "function" | "property" | "class" | "exception":
            if isinstance(obj, property):
                obj = obj.fget
            if hasattr(obj, ATTR_DEPRECATED) and isinstance(msg := getattr(obj, ATTR_DEPRECATED, None), Deprecation):
                _process_deprecated_function(app, msg, lines)
            if (args := getattr(obj, ATTR_DEPRECATED_ARG, None)) is not None:
                _process_deprecated_args(args, lines)
        case "data" if isinstance(obj, Settings):
            _process_settings_object(obj, name, lines)


def _emit_docstring(app: Sphinx, model: Docstring, lines: list[str]) -> None:
    """Emit a docstring compatible with the user settings (i.e. renderable with the chosen napoleon settings)."""
    if getattr(app.config, "napoleon_google_docstring", True):
        doc = emit_google(model)
    elif getattr(app.config, "napoleon_numpy_docstring", True):
        doc = emit_numpy(model)
    else:
        warnings.warn(
            "Neither Google-style nor Numpy-style docstrings are enabled. Skipping docstring generation.", stacklevel=2
        )
        return
    lines[:] = doc.strip("\n").splitlines()


def _process_deprecated_function(app: Sphinx, msg: Deprecation, lines: list[str]) -> None:
    parsed = parse("\n".join(lines))

    model = parsed.to_model()
    notice = f".. version-deprecated:: {msg.version_deprecated}"
    if len(msg):
        notice += f"\n{textwrap.indent(msg._docmsg or '', 3 * ' ')}"
    if model.extended_summary is not None:
        notice += f"\n\n{model.extended_summary}"
    model.extended_summary = notice
    _emit_docstring(app, model, lines)


def _process_deprecated_args(deprecations: list[deprecated_arg], lines: list[str]) -> None:
    parsed = parse("\n".join(lines))
    if parsed.style is Style.PLAIN:
        return

    model = parsed.to_model()
    if found := next(
        (
            (s, section, p, par, deprecation)
            for s, section in enumerate(model.sections)
            if section.kind in {SectionKind.PARAMETERS, SectionKind.KEYWORD_PARAMETERS, SectionKind.OTHER_PARAMETERS}
            for p, par in enumerate(section.parameters)
            for deprecation in deprecations
            if deprecation.arg in par.names
        ),
        None,
    ):
        s, section, p, par, deprecation = found

        docmsg = f".. version-deprecated:: {deprecation.msg.version_deprecated}"
        if len(deprecation.msg):
            docmsg += f"\n   {deprecation.msg}"
        if par.description is not None:
            docmsg += f"\n\n{par.description}"
        par.description = docmsg
        params = list(section.parameters)
        params[p] = par
        sections = model.sections
        sections[s] = Section(section.kind, parameters=params)
        model.sections = sections
    match parsed.style:
        case Style.GOOGLE:
            doc = emit_google(model)
        case Style.NUMPY:
            doc = emit_numpy(model)
        case _:  # pragma: no cover
            raise AssertionError

    lines[:] = doc.strip("\n").splitlines()


_settings_docstring_template = """Allows users to customize settings for the `{package}` package.

Settings here will generally be for advanced use-cases and should be used with caution.

For setting an option use :func:`~{name}.override` (local) or set the attributes directly (global)
e.g., `{name}.my_setting = foo`. For assignment by environment variable, use the variable name in
all caps with `{env_prefix}` as the prefix before import of `{package}`.

The following options are available:

"""


def _get_objname(name: str) -> str:
    dotidx = name.rfind(".")
    if dotidx > -1:
        name = name[dotidx + 1 :]
    return name


def _process_settings_object(settings: Settings, name: str, lines: list[str]) -> None:
    package = get_packagename(name)

    doc = _settings_docstring_template.format(
        package=package,
        name=name,
        env_prefix=settings.model_config["env_prefix"].upper(),
    ).splitlines()

    objname = _get_objname(name)
    for fname, field in settings.__class__.model_fields.items():
        doc.append(f".. attribute:: {objname}.{fname}")
        doc.append(f"   :type: {type_str(type(settings), field)}")

        if field.default is not PydanticUndefined:
            doc.append(f"   :value: {field.default!r}")

        deprecation_version = "???"
        deprecation_msg = None
        match field.deprecated:
            case deprecated():
                deprecation_msg = field.deprecated.message
                if isinstance(field.deprecated.message, Deprecation):
                    deprecation_version = field.deprecated.message.version_deprecated
            case str():
                deprecation_msg = field.deprecated
            case True:
                deprecation_msg = ""
        if deprecation_msg is not None:
            doc.append("")
            doc.append(f"   .. version-deprecated:: {deprecation_version}")
            doc.append(indent(deprecation_msg, 6 * " "))

        if field.description is not None:
            doc.append("")
            doc.append(f"{textwrap.indent(field.description, '   ')}")

    lines[:] = doc


def _process_settings_method(app: Sphinx, method: MethodType, lines: list[str]) -> None:
    match method.__name__:
        case "override":
            _process_settings_method_override(app, method, lines)
        case "reset":
            _process_settings_method_reset(app, method, lines)
        case _:
            raise AssertionError


def _process_settings_method_override(app: Sphinx, method: MethodType, lines: list[str]) -> None:
    settings = cast("Settings", method.__self__)
    params = [
        Parameter([fname], type_annotation=type_str(type(settings), field), description=field.description)
        for fname, field in type(settings).model_fields.items()
    ]
    model = Docstring(
        summary="Provides local override via keyword arguments as a context manager.",
        sections=[Section(SectionKind.PARAMETERS, parameters=params)],
    )
    _emit_docstring(app, model, lines)


def _process_settings_method_reset(app: Sphinx, method: MethodType, lines: list[str]) -> None:
    settings = cast("Settings", method.__self__)
    names_param = Parameter(
        ["names"], type_annotation=f"typing.Literal[{', '.join(settings.model_fields.keys())}]", is_optional=True
    )
    model = Docstring(summary=method.__doc__, sections=[Section(SectionKind.PARAMETERS, parameters=[names_param])])
    _emit_docstring(app, model, lines)


_namespace_decorator_summary_template = (
    "Decorator for registering custom functionality with a :class:`~{qualname}` object."
)
_namespace_decorator_extended_summary_template = """This decorator allows you to extend {name} objects with custom methods and properties
organized under a namespace. The namespace becomes accessible as an attribute on {name}
instances, providing a clean way to you to add domain-specific functionality without modifying
the {name} class itself, or extending the class with additional methods as you see fit in your workflow."""
_namespace_decorator_argument_description_template = """Name under which the accessor should be registered. This will be the attribute name
used to access your namespace's functionality on {name} objects (e.g., `instance.name`).
Cannot conflict with existing {name} attributes. The list of reserved attributes includes
everything outputted by `dir({name})`."""
_namespace_decorator_notes_template = """Implementation requirements:

1. The decorated class must have an `__init__` method that accepts exactly one parameter
   (besides `self`) named `{canonical_instance_name}` and annotated with type :class:`~{qualname}`.
2. The namespace will be initialized with the {name} object on first access and then
   cached on the instance.
3. If the namespace name conflicts with an existing namespace, a warning is issued.
4. If the namespace name conflicts with a built-in {name} attribute, an AttributeError is raised.",
"""
_namespace_decorator_examples_template = """>>> @{decorator_name}("do_something")
... class DoSomething:
...     def __init__(self, {canonical_instance_name}: {name}):
...         self._obj = {canonical_instance_name}
...
...     def has_foo(self) -> bool:
...         return hasattr(self._obj, "foo")
>>>
>>> # Create a {name} object
>>> obj = {name}()
>>>
>>> # use the registered namespace
>>> obj.do_something.has_foo()
False
"""


def _process_namespace_decorator(app: Sphinx, name: str, info: _NSInfo, lines: list[str]) -> None:
    qualname = f"{info.cls.__module__}.{info.cls.__name__}"
    model = Docstring(
        summary=_namespace_decorator_summary_template.format(qualname=qualname),
        extended_summary=_namespace_decorator_extended_summary_template.format(name=info.cls.__name__),
        sections=[
            Section(
                SectionKind.PARAMETERS,
                parameters=[
                    Parameter(
                        names=["name"],
                        description=_namespace_decorator_argument_description_template.format(name=info.cls.__name__),
                    )
                ],
            ),
            Section(
                SectionKind.RETURNS,
                returns=[Return(description="A decorator that registers the decorated class as a custom namespace.")],
            ),
            Section(
                SectionKind.NOTES,
                body=_namespace_decorator_notes_template.format(
                    qualname=qualname, name=info.cls.__name__, canonical_instance_name=info.name
                ),
            ),
            Section(
                SectionKind.EXAMPLES,
                body=_namespace_decorator_examples_template.format(
                    decorator_name=_get_objname(name), name=info.cls.__name__, canonical_instance_name=info.name
                ),
            ),
        ],
    )

    _emit_docstring(app, model, lines)
