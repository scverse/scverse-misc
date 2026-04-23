from __future__ import annotations

import inspect
from typing import Annotated

import pytest
from pydantic import Field, ValidationError
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict

from scverse_misc import Settings


class DummySettings(Settings, exported_object_name="settings", docstring_style="google"):
    model_config = SettingsConfigDict(validate_assignment=False)

    field_bool: bool = False
    """Boolean field."""

    field_no_docstring: int = 42

    field_int_range: Annotated[int, Field(ge=0, le=4)] = 1
    """Integer range field."""


@pytest.fixture
def settings() -> DummySettings:
    return DummySettings()


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


def test_docs(settings: DummySettings) -> None:
    lines = (inspect.getdoc(settings) or "").splitlines()
    assert lines[0].endswith("`tests` package.")

    current_field: FieldInfo | None = None
    field_iter = iter(settings.__class__.model_fields.items())
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


def test_override_docs(settings: DummySettings) -> None:
    lines = (inspect.getdoc(settings.override) or "").splitlines()
    assert lines[2] == "Args:"
    for line, (field_name, field) in zip(lines[3:], settings.__class__.model_fields.items(), strict=True):
        assert field.annotation is not None
        assert line.startswith(f"    {field_name} ({str(field.annotation.__name__)})")

        line_end = f" (default `{field.default!r}`) "
        if field.description is not None:
            line_end += field.description
        assert line.endswith(line_end)
