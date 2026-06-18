from __future__ import annotations

import textwrap
import warnings
from collections.abc import Callable
from importlib.metadata import version
from types import FunctionType, GenericAlias, MethodType
from typing import TYPE_CHECKING, Any, cast

from pydocstring import Docstring, Parameter, Return, Section, SectionKind, Style, emit_google, emit_numpy, parse

from .._deprecated import Deprecation, deprecated_arg
from .._utils import get_packagename, type_str

try:
    from pydantic_core import PydanticUndefined

    from .._settings import Settings
except ImportError:
    pass


if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.ext.autodoc import Options as AutodocOptions
    from sphinx.ext.autodoc import _AutodocObjType  # type: ignore[attr-defined]
    from sphinx.util.typing import ExtensionMetadata


def setup(app: Sphinx) -> ExtensionMetadata:  # noqa: D103
    app.setup_extension("sphinx.ext.autodoc")
    app.connect("autodoc-process-docstring", _process_docstring)

    return {"version": version("scverse-misc"), "parallel_read_safe": True}


def _process_docstring(
    app: Sphinx, objtype: _AutodocObjType, name: str, obj: object, options: AutodocOptions, lines: list[str]
) -> None:
    match objtype:
        case "function" if hasattr(obj, "__scverse_misc_create_namespace__") and hasattr(
            obj, "__scverse_misc_canonical_instance_name__"
        ):
            assert isinstance(obj.__scverse_misc_create_namespace__, type)
            assert isinstance(obj.__scverse_misc_canonical_instance_name__, str)
            _process_namespace_decorator(
                app, name, obj.__scverse_misc_create_namespace__, obj.__scverse_misc_canonical_instance_name__, lines
            )
        case "method" | "function" if isinstance(obj, MethodType) and isinstance(obj.__self__, Settings):
            _process_settings_method(app, obj, lines)
        case "function" | "method" | "class":
            if hasattr(obj, "__deprecated__") and isinstance(obj.__deprecated__, Deprecation):
                _process_deprecated_function(app, obj.__deprecated__, lines)
            if (args := getattr(obj, "__scverse_misc_deprecated_arg__", None)) is not None:
                _process_deprecated_args(args, lines)
        case "property" if (
            hasattr(obj, "fget")
            and hasattr(obj.fget, "__deprecated__")
            and isinstance(obj.fget.__deprecated__, Deprecation)
        ):
            _process_deprecated_function(app, obj.fget.__deprecated__, lines)
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

    params = []
    for fname, field in type(settings).model_fields.items():
        param = Parameter([fname], type_annotation=type_str(type(settings), field), description=field.description)
        if field.default is not PydanticUndefined:
            param.default_value = repr(field.default)
        params.append(param)

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


def _process_namespace_decorator(
    app: Sphinx, name: str, cls: type, canonical_instance_name: str, lines: list[str]
) -> None:
    qualname = f"{cls.__module__}.{cls.__name__}"
    model = Docstring(
        summary=_namespace_decorator_summary_template.format(qualname=qualname),
        extended_summary=_namespace_decorator_extended_summary_template.format(name=cls.__name__),
        sections=[
            Section(
                SectionKind.PARAMETERS,
                parameters=[
                    Parameter(
                        names=["name"],
                        description=_namespace_decorator_argument_description_template.format(name=cls.__name__),
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
                    qualname=qualname, name=cls.__name__, canonical_instance_name=canonical_instance_name
                ),
            ),
            Section(
                SectionKind.EXAMPLES,
                body=_namespace_decorator_examples_template.format(
                    decorator_name=_get_objname(name),
                    name=cls.__name__,
                    canonical_instance_name=canonical_instance_name,
                ),
            ),
        ],
    )

    _emit_docstring(app, model, lines)
