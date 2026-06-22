from __future__ import annotations

import inspect
import sys
from typing import Annotated

if sys.version_info >= (3, 13):
    from warnings import deprecated as stdlib_deprecated
else:
    from typing_extensions import deprecated as stdlib_deprecated

import pytest

pytest.importorskip("scverse_misc.sphinx_ext")
from pydantic import Field
from pydantic.fields import FieldInfo
from sphinx.application import Sphinx
from sphinx.ext.autodoc import Options as AutodocOptions
from sphinx.ext.napoleon.docstring import GoogleDocstring, NumpyDocstring

from scverse_misc import Deprecation, Settings, deprecated
from scverse_misc.sphinx_ext import _process_docstring


class DummySettings(Settings):
    field_bool: bool = False
    """Boolean field."""

    field_no_docstring: int = 42

    field_int_range: Annotated[int, Field(ge=0, le=4)] = 1
    """Integer range field."""


def test_body(app: Sphinx, parser: type[GoogleDocstring | NumpyDocstring]) -> None:
    settings = DummySettings()
    lines = (inspect.getdoc(settings) or "").splitlines()
    _process_docstring(app, "data", "tests.settings", settings, AutodocOptions(), lines)
    lines = parser(lines).lines()

    assert lines[0].endswith("`tests` package.")

    current_field: FieldInfo | None = None
    field_iter = iter(type(settings).model_fields.items())
    for line in lines:
        if line.startswith(".. attribute::"):
            current_field_name, current_field = next(field_iter)
            assert line.endswith(current_field_name)
        elif current_field is not None:
            line = line.strip()
            if line.startswith(":type:"):
                assert current_field.annotation is not None
                assert line.endswith(current_field.annotation.__name__)
            elif line.startswith(":value:"):
                assert line.endswith(repr(current_field.default))
            elif len(line) > 0 and current_field.description is not None:
                assert line == current_field.description

    assert not list(field_iter)


def test_override(subtests: pytest.Subtests, app: Sphinx, parser: type[GoogleDocstring | NumpyDocstring]) -> None:
    settings = DummySettings()
    lines = (inspect.getdoc(settings.override) or "").splitlines()
    _process_docstring(app, "method", "tests.settings.override", settings.override, AutodocOptions(), lines)
    lines = parser(lines).lines()

    current_field: FieldInfo | None = None
    field_iter = iter(type(settings).model_fields.items())
    for line in lines:
        if line.startswith(":param"):
            current_field_name, current_field = next(field_iter)
            description = f" {current_field.description}" if current_field.description is not None else ""
            with subtests.test(current_field_name):
                # no default here, as the default is “leave this value alone”
                assert line.startswith(f":param {current_field_name}:{description}")
        elif current_field is not None and len(line) > 0:
            assert current_field.annotation is not None
            with subtests.test(current_field_name, what="type"):
                assert line == f":type {current_field_name}: {current_field.annotation.__name__}"

    assert not list(field_iter)


@pytest.mark.parametrize("enable_s_a_t", [True, False], ids=["s_a_t", "no_s_a_t"])
def test_override_s_a_t(app: Sphinx, parser: type[GoogleDocstring | NumpyDocstring], enable_s_a_t: bool) -> None:
    """Test that `:type <param>:` isn’t added (by us!) when `sphinx_autodoc_typehints` is enabled."""
    if enable_s_a_t:
        app.setup_extension("sphinx_autodoc_typehints")
    settings = DummySettings()
    lines = (inspect.getdoc(settings.override) or "").splitlines()
    _process_docstring(app, "method", "tests.settings.override", settings.override, AutodocOptions(), lines)
    lines = parser(lines).lines()

    assert ":param field_bool: Boolean field." in lines
    assert (":type" not in "\n".join(lines)) == enable_s_a_t


@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        pytest.param("string", "str", id="builtin"),
        pytest.param("pattern", "re.Pattern[str]", id="import"),
        # same module as `S`, so no leading `tests.test_settings.`
        pytest.param("local", "test_annotation_format.<locals>.Local", id="same-module"),
    ],
)
def test_annotation_format(
    app: Sphinx, parser: type[GoogleDocstring | NumpyDocstring], attr: str, expected: str
) -> None:
    """Test that annotation references work correctly."""
    import re

    class Local: ...

    class S(Settings):
        if attr == "string":
            string: str = "abc"
        if attr == "pattern":
            pattern: re.Pattern[str] = re.compile("abc")
        if attr == "local":
            local: Local = Local()

    settings = S()

    lines = (inspect.getdoc(settings) or "").splitlines()
    _process_docstring(app, "data", "tests.settings", settings, AutodocOptions(), lines)
    lines = parser(lines).lines()
    lines = lines[lines.index(f".. attribute:: settings.{attr}") + 1 :]

    assert lines[0] == f"   :type: {expected}"


@pytest.mark.parametrize(
    ("deprecation", "expected_version", "expected_msg"),
    (
        (
            deprecated(Deprecation("0.4.2", "This setting does not do anything.")),
            "0.4.2",
            "This setting does not do anything.",
        ),
        (
            stdlib_deprecated(Deprecation("0.4.2", "This setting does not do anything")),
            "0.4.2",
            "This setting does not do anything",
        ),
        (stdlib_deprecated("This setting does not do anything"), "???", "This setting does not do anything"),
        ("This setting does not do anything", "???", "This setting does not do anything"),
        (True, "???", ""),
    ),
)
def test_deprecation(
    app: Sphinx,
    parser: type[GoogleDocstring | NumpyDocstring],
    deprecation: deprecated | str | bool,
    expected_version: str,
    expected_msg: str,
) -> None:
    class S(Settings):
        field_deprecated: Annotated[float, Field(deprecated=deprecation)] = 3.14
        """A deprecated setting."""

    settings = S()

    lines = (inspect.getdoc(settings) or "").splitlines()
    _process_docstring(app, "data", "tests.settings", settings, AutodocOptions(), lines)
    lines = parser(lines).lines()
    lines = lines[lines.index(".. attribute:: settings.field_deprecated") + 4 :]

    assert lines[0] == f"   .. version-deprecated:: {expected_version}"
    assert lines[1] == (f"      {expected_msg}" if len(expected_msg) > 0 else "")
