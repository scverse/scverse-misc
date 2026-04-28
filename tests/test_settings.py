from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, cast

import pytest
from pydantic import Field, ValidationError
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict
from sphinx.application import Sphinx
from sphinx.ext.napoleon import GoogleDocstring, NumpyDocstring  # type: ignore[attr-defined]

from scverse_misc import Settings

if TYPE_CHECKING:
    # Static version of the class returned by the `settings_class` fixture
    class DummySettings(Settings, exported_object_name="settings"):
        field_bool: bool = False
        field_no_docstring: int = 42
        field_int_range: int = 1


pytest_plugins = ["sphinx.testing.fixtures"]


@pytest.fixture
def docstring_style(request: pytest.FixtureRequest) -> Literal["google", "numpy", "scverse"]:
    return getattr(request, "param", "google")


@pytest.fixture
def settings_class(docstring_style: Literal["google", "numpy", "scverse"]) -> type[DummySettings]:
    class _DummySettings(Settings, exported_object_name="settings", docstring_style=docstring_style):
        field_bool: bool = False
        """Boolean field."""

        field_no_docstring: int = 42

        field_int_range: Annotated[int, Field(ge=0, le=4)] = 1
        """Integer range field."""

    return cast("type[DummySettings]", _DummySettings)


@pytest.fixture
def settings(settings_class: type[DummySettings]) -> DummySettings:
    return settings_class()


def test_defaults_override() -> None:
    with (
        pytest.warns(RuntimeWarning, match="validate_assignment=False"),
        pytest.warns(RuntimeWarning, match="use_attribute_docstrings=False"),
        pytest.warns(RuntimeWarning, match="custom env_file location"),
    ):

        class WarnSettings(Settings, exported_object_name="settings", docstring_style="google"):
            model_config = SettingsConfigDict(
                validate_assignment=False, use_attribute_docstrings=False, env_file="mydotenv"
            )

            field_bool: bool = False

    settings = WarnSettings()
    with pytest.raises(ValidationError):
        settings.field_bool = 2  # type: ignore[assignment]


@pytest.mark.parametrize("v", [2, 4])
def test_env_vars(monkeypatch: pytest.MonkeyPatch, settings_class: type[DummySettings], v: int) -> None:
    """Test that the env var prefix is derived from the module name."""
    monkeypatch.setenv("TESTS_FIELD_INT_RANGE", str(v))
    settings = settings_class()
    assert settings.field_int_range == v


def test_validate_assignment(settings: DummySettings) -> None:
    with pytest.raises(ValidationError):
        settings.field_bool = 2  # type: ignore[assignment]
    with pytest.raises(ValidationError):
        settings.field_int_range = -1


def test_override(settings: DummySettings) -> None:
    with settings.override(field_bool=True):
        assert settings.field_bool is True
    assert settings.field_bool is False

    with pytest.raises(ValidationError):
        with settings.override(field_int_range=3, field_no_docstring=1.1):
            pass
    assert settings.field_no_docstring == 42
    assert settings.field_int_range == 1


@pytest.mark.parametrize("docstring_style", ["google", "numpy", "scverse"], indirect=True)
def test_docs(docstring_style: Literal["google", "numpy"], settings: DummySettings) -> None:
    parser = GoogleDocstring if docstring_style == "google" else NumpyDocstring
    lines = parser(inspect.getdoc(settings) or "").lines()

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


@pytest.mark.parametrize("docstring_style", ["google", "numpy", "scverse"], indirect=True)
def test_override_docs(docstring_style: Literal["google", "numpy"], settings: DummySettings) -> None:
    parser = GoogleDocstring if docstring_style == "google" else NumpyDocstring
    lines = parser(inspect.getdoc(settings.override) or "").lines()

    current_field: FieldInfo | None = None
    field_iter = iter(type(settings).model_fields.items())
    for line in lines:
        if line.startswith(":param"):
            current_field_name, current_field = next(field_iter)
            description = f" {current_field.description}" if current_field.description is not None else ""
            # no default here, as the default is “leave this value alone”
            assert line.startswith(f":param {current_field_name}:{description}")
        elif current_field is not None and len(line) > 0:
            assert current_field.annotation is not None
            assert line == f":type {current_field_name}: {current_field.annotation.__name__}"


@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        pytest.param("string", "str", id="builtin"),
        pytest.param("path", "pathlib.Path", id="3rd-party"),
        # same module as `S`, so no leading `tests.test_settings.`
        pytest.param("local", "test_annotation_format.<locals>.Local", id="same-module"),
    ],
)
def test_annotation_format(attr: str, expected: str) -> None:
    """Test that annotation references work correctly."""

    class Local: ...

    class S(Settings, exported_object_name="s", docstring_style="google"):
        if attr == "string":
            string: str
        if attr == "path":
            path: Path
        if attr == "local":
            local: Local

    lines = (inspect.getdoc(S) or "").splitlines()
    lines = lines[lines.index(f".. attribute:: s.{attr}") + 1 :]

    assert lines == [f"   :type: {expected}"]


@pytest.fixture(scope="session", autouse=True)
def _sphinx_config(sphinx_test_tempdir: Path) -> None:
    """Since we only need one, we use this instead of static roots like `@pytest.mark.sphinx('html', testroot="mybook")`."""
    p = sphinx_test_tempdir / "root" / "conf.py"
    p.parent.mkdir(parents=True)
    p.write_text("""
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx_autodoc_typehints"]
typehints_defaults = "braces"
""")


@pytest.mark.parametrize("docstring_style", ["scverse"])
@pytest.mark.parametrize("parent", ["class", "object"])
def test_sphinx_autodoc_typehints(
    subtests: pytest.Subtests,
    app: Sphinx,
    settings_class: type[DummySettings],
    settings: DummySettings,
    parent: Literal["class", "object"],
) -> None:
    import sphinx.ext.napoleon
    import sphinx_autodoc_typehints

    obj = (settings if parent == "object" else settings_class).override
    lines = (inspect.getdoc(obj) or "").splitlines()
    lines = sphinx.ext.napoleon.NumpyDocstring(lines, app.config, app, "method", "", obj).lines()

    with subtests.test("napoleon"):
        # test that napoleon can parse things correctly
        # especially the last parameter could fail to parse if there are not enough trailing newlines
        for name in settings_class.model_fields:
            assert f":param {name}:" in "\n".join(lines)

    sphinx_autodoc_typehints.process_docstring(app, "method", "", obj, options=None, lines=lines)

    with subtests.test("type"):  # no need to test all parameters
        assert (
            r":type field_bool: :sphinx_autodoc_typehints_type:`\:py\:class\:\`bool\`` (default: ``<no change>``)"
            in lines
        )
    with subtests.test("rtype"):
        assert (
            r":rtype: :sphinx_autodoc_typehints_type:`\:py\:class\:\`\~contextlib.AbstractContextManager\`\\ \\\[\:py\:obj\:\`None\`\]`"
            in lines
        )
