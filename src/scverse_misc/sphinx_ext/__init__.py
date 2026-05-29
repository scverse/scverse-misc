from __future__ import annotations

import textwrap
import warnings
from types import FunctionType, GenericAlias, MethodType
from typing import TYPE_CHECKING, Any, cast

from pydantic_core import PydanticUndefined
from pydocstring import Docstring, Parameter, Section, SectionKind, Style, emit_google, emit_numpy, parse

from .._deprecated import Deprecation, deprecated_arg
from .._settings import Settings
from .._utils import get_packagename
from .._version import __version__

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo
    from sphinx.application import Sphinx
    from sphinx.ext.autodoc import Options as AutodocOptions
    from sphinx.ext.autodoc import _AutodocObjType  # type: ignore[attr-defined]
    from sphinx.util.typing import ExtensionMetadata


def setup(app: Sphinx) -> ExtensionMetadata:  # noqa: D103
    app.setup_extension("sphinx.ext.autodoc")
    app.connect("autodoc-process-docstring", _process_docstring)

    return {"version": __version__, "parallel_read_safe": True}


def _process_docstring(
    app: Sphinx, objtype: _AutodocObjType, name: str, obj: Any, options: AutodocOptions, lines: list[str]
) -> None:
    match objtype:
        case "function" | "method" | "class":
            if hasattr(obj, "__deprecated__") and isinstance(obj.__deprecated__, Deprecation):
                _process_deprecated_function(app, obj.__deprecated__, lines)
            if hasattr(obj, "__scverse_misc_deprecated_arg__"):
                _process_deprecated_args(obj.__scverse_misc_deprecated_arg__, lines)
        case "property" if hasattr(obj.fget, "__deprecated__") and isinstance(obj.fget.__deprecated__, Deprecation):
            _process_deprecated_function(app, obj.fget.__deprecated__, lines)
        case "data" if isinstance(obj, Settings):
            _process_settings_object(obj, name, lines)
        case "method" if isinstance(obj, MethodType) and isinstance(obj.__self__, Settings):
            _process_settings_method(app, obj, lines)


def _process_deprecated_function(app: Sphinx, msg: Deprecation, lines: list[str]) -> None:
    parsed = parse("\n".join(lines))

    model = parsed.to_model()
    notice = f".. version-deprecated:: {msg.version_deprecated}"
    if len(msg):
        notice += f"\n{textwrap.indent(msg._docmsg or '', 3 * ' ')}"
    model = Docstring(
        summary=model.summary,
        extended_summary=notice + f"\n\n{model.extended_summary}",
        deprecation=model.deprecation,
        sections=model.sections,
    )

    if getattr(app.config, "napoleon_google_docstring", True):
        doc = emit_google(model)
    elif getattr(app.config, "napoleon_numpy_docstring", True):
        doc = emit_numpy(model)
    else:
        warnings.warn(
            "Neither Google-style nor Numpy-style docstrings are enabled. Skipping docstring generation.", stacklevel=1
        )
        return

    lines[:] = doc.strip("\n").splitlines()


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
        sections = list(model.sections)
        sections[s] = Section(section.kind, parameters=params)
        model = Docstring(
            summary=model.summary,
            extended_summary=model.extended_summary,
            deprecation=model.deprecation,
            sections=sections,
        )
    match parsed.style:
        case Style.GOOGLE:
            doc = emit_google(model)
        case Style.NUMPY:
            doc = emit_numpy(model)
        case _:  # pragma: no cover
            raise AssertionError

    lines[:] = doc.strip("\n").splitlines()


def _type_str(cls: object, field: FieldInfo) -> str:
    if isinstance(field.annotation, GenericAlias) or not isinstance(field.annotation, type):
        return str(field.annotation)
    if field.annotation.__module__ in {"builtins", cls.__module__}:
        return field.annotation.__qualname__
    return f"{field.annotation.__module__}.{field.annotation.__qualname__}"


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
        doc.append(f"   :type: {_type_str(settings, field)}")

        if field.default is not PydanticUndefined:
            doc.append(f"   :value: {field.default!r}")
        if field.description is not None:
            doc.append("")
            doc.append(f"{textwrap.indent(field.description, '   ')}")

    lines[:] = doc


def _process_settings_method(app: Sphinx, settings: MethodType, lines: list[str]) -> None:
    if settings.__name__ != "override":
        return

    settingsobj = cast(Settings, settings.__self__)

    params = []
    for fname, field in settingsobj.__class__.model_fields.items():
        param = Parameter(names=[fname], type_annotation=_type_str(settingsobj, field), description=field.description)
        if field.default is not PydanticUndefined:
            param.default_value = repr(field.default)
        params.append(param)

    model = Docstring(
        summary="Provides local override via keyword arguments as a context manager.",
        sections=[Section(SectionKind.PARAMETERS, parameters=params)],
    )
    if getattr(app.config, "napoleon_google_docstring", True):
        doc = emit_google(model)
    elif getattr(app.config, "napoleon_numpy_docstring", True):
        doc = emit_numpy(model)
    else:
        warnings.warn(
            "Neither Google-style nor Numpy-style docstrings are enabled. Skipping docstring generation.", stacklevel=1
        )
        doc = ""
    lines[:] = doc.strip("\n").splitlines()
