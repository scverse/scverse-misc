from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Annotated, Literal, cast

import pytest
from pydantic import Field, ValidationError
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict
from sphinx.ext.napoleon import GoogleDocstring, NumpyDocstring  # type: ignore[attr-defined]

from scverse_misc import Settings

if TYPE_CHECKING:
    # Static version of the class returned by the `settings_class` fixture
    class DummySettings(Settings, exported_object_name="settings"):
        field_bool: bool = False
        field_no_docstring: int = 42
        field_int_range: int = 1


@pytest.fixture
def docstring_style(request: pytest.FixtureRequest) -> Literal["google", "numpy"]:
    return getattr(request, "param", "google")


@pytest.fixture
def settings_class(docstring_style: Literal["google", "numpy"]) -> type[DummySettings]:
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

        class WarnSettings(Settings, exported_object_name="settings"):
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


@pytest.mark.parametrize("docstring_style", ["google", "numpy"], indirect=True)
def test_docs(docstring_style: Literal["google", "numpy"], settings: DummySettings) -> None:
    parser = GoogleDocstring if docstring_style == "google" else NumpyDocstring
    lines = parser(inspect.getdoc(settings)).lines()  # type: ignore[arg-type]

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


@pytest.mark.parametrize("docstring_style", ["google", "numpy"], indirect=True)
def test_override_docs(docstring_style: Literal["google", "numpy"], settings: DummySettings) -> None:
    parser = GoogleDocstring if docstring_style == "google" else NumpyDocstring
    lines = parser(inspect.getdoc(settings.override)).lines()  # type: ignore[arg-type]

    current_field: FieldInfo | None = None
    field_iter = iter(type(settings).model_fields.items())
    for line in lines:
        if line.startswith(":param"):
            current_field_name, current_field = next(field_iter)
            description = " " + current_field.description if current_field.description is not None else ""
            assert line.startswith(f":param {current_field_name}: (default `{current_field.default!r}`){description}")
        elif current_field is not None and len(line) > 0:
            assert line == f":type {current_field_name}: {current_field.annotation.__name__}"  # type: ignore[union-attr]
