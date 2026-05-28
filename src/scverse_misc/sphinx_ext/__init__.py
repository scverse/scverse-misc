from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydocstring import Docstring, Section, SectionKind, Style, emit_google, emit_numpy, parse

from .._deprecated import deprecated_arg
from .._version import __version__

if TYPE_CHECKING:
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
        case "function" | "class" if hasattr(obj, "__scverse_misc_deprecated_arg__"):
            _process_deprecated_args(obj.__scverse_misc_deprecated_arg__, lines)


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

    lines[:] = doc.splitlines()
