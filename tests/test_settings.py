from __future__ import annotations

import inspect
import sys
from collections.abc import Callable
from contextlib import chdir, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, cast, get_args

import pytest
from pydantic import Field, ValidationError
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict
from sphinx.ext.napoleon import GoogleDocstring, NumpyDocstring  # type: ignore[attr-defined]

from scverse_misc import Settings, sphinx_ext

if TYPE_CHECKING:
    # Static version of the class returned by the `settings_class` fixture
    class DummySettings(Settings):
        field_bool: bool = False
        field_no_docstring: int = 42
        field_int_range: int = 1


@pytest.fixture
def docstring_style(request: pytest.FixtureRequest) -> Literal["google", "numpy"]:
    return getattr(request, "param", "google")


@pytest.fixture
def settings_class_factory(docstring_style: Literal["google", "numpy"]) -> Callable[[], type[DummySettings]]:
    def settings_class() -> type[DummySettings]:
        class _DummySettings(Settings, exported_object_name="settings", docstring_style=docstring_style):
            field_bool: bool = False
            """Boolean field."""

            field_no_docstring: int = 42

            field_int_range: Annotated[int, Field(ge=0, le=4)] = 1
            """Integer range field."""

        return cast("type[DummySettings]", _DummySettings)

    return settings_class


@pytest.fixture
def settings_class(settings_class_factory: Callable[[], type[DummySettings]]) -> type[DummySettings]:
    return settings_class_factory()


@pytest.fixture
def settings(settings_class: type[DummySettings]) -> DummySettings:
    return settings_class()


def test_defaults_override() -> None:
    with (
        pytest.warns(RuntimeWarning, match="validate_assignment=False"),
        pytest.warns(RuntimeWarning, match="use_attribute_docstrings=False"),
        pytest.warns(RuntimeWarning, match="custom env_file location"),
        pytest.warns(RuntimeWarning, match="dotenv_filtering scheme"),
    ):

        class WarnSettings(Settings):
            model_config = SettingsConfigDict(
                validate_assignment=False,
                use_attribute_docstrings=False,
                env_file="mydotenv",
                dotenv_filtering="match_prefix",
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


@pytest.mark.parametrize("v", [2, 4])
def test_dotenv(settings_class_factory: Callable[[], type[DummySettings]], v: int, tmp_path: Path) -> None:
    env = f"""\
SOMEVAR=true
TESTS_FIELD_INT_RANGE={v}
TESTS_DOES_NOT_EXIST=42
"""
    with open(tmp_path / ".env", "w") as dotenv:
        dotenv.write(env)

    with chdir(tmp_path):
        settings = settings_class_factory()()
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


def test_override_error(settings: DummySettings) -> None:
    with pytest.raises(ValidationError):
        with settings.override(field_int_range=3, field_no_docstring=1.1):
            pass
    assert settings.field_no_docstring == 42
    assert settings.field_int_range == 1


@pytest.mark.parametrize("temp", [True, False], ids=["temporary", "permanent"])
def test_reset(settings: DummySettings, temp: bool) -> None:
    default = settings.field_bool
    settings.field_bool = not default
    undo_reset = settings.reset("field_bool")
    with undo_reset if temp else nullcontext():
        assert settings.field_bool is default
    assert settings.field_bool is (not default if temp else default)


def test_reset_signature(settings: DummySettings) -> None:
    sig = inspect.signature(settings.reset)
    assert get_args(sig.parameters["args"].annotation) == ("field_bool", "field_no_docstring", "field_int_range")


@pytest.mark.skipif(sys.version_info < (3, 14), reason="requires annotationlib")
def test_reset_annotations(settings: DummySettings) -> None:
    from contextlib import AbstractContextManager

    import annotationlib

    assert annotationlib.get_annotations(settings.reset) == {
        "args": Literal["field_bool", "field_no_docstring", "field_int_range"],
        "return": AbstractContextManager[frozenset[Literal["field_bool", "field_no_docstring", "field_int_range"]]],
    }


@pytest.mark.parametrize("docstring_style", ["google", "numpy"], indirect=True)
def test_docs(docstring_style: Literal["google", "numpy"], settings: DummySettings) -> None:
    parser = GoogleDocstring if docstring_style == "google" else NumpyDocstring

    lines = (inspect.getdoc(settings) or "").splitlines()
    sphinx_ext._process_settings_object(settings, "tests.settings", lines)
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


@pytest.mark.parametrize("docstring_style", ["google", "numpy"], indirect=True)
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
        pytest.param("pattern", "re.Pattern[str]", id="import"),
        # same module as `S`, so no leading `tests.test_settings.`
        pytest.param("local", "test_annotation_format.<locals>.Local", id="same-module"),
    ],
)
def test_annotation_format(attr: str, expected: str) -> None:
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
    sphinx_ext._process_settings_object(settings, "tests.s", lines)
    lines = lines[lines.index(f".. attribute:: s.{attr}") + 1 :]

    assert lines[0] == f"   :type: {expected}"
