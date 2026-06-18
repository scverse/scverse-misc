from __future__ import annotations

import inspect
import sys
from contextlib import chdir, nullcontext
from pathlib import Path
from typing import Annotated, Literal, get_args, get_origin

import pytest
from pydantic import Field, ValidationError
from pydantic_settings import SettingsConfigDict

from scverse_misc import Settings


class DummySettings(Settings):
    field_bool: bool = False
    field_int: int = 42
    field_int_range: Annotated[int, Field(ge=0, le=4)] = 1


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
def test_env_vars(monkeypatch: pytest.MonkeyPatch, v: int) -> None:
    """Test that the env var prefix is derived from the module name."""
    monkeypatch.setenv("TESTS_FIELD_INT_RANGE", str(v))
    settings = DummySettings()
    assert settings.field_int_range == v


@pytest.mark.parametrize("v", [2, 4])
def test_dotenv(v: int, tmp_path: Path) -> None:
    env = f"""\
SOMEVAR=true
TESTS_FIELD_INT_RANGE={v}
TESTS_DOES_NOT_EXIST=42
"""
    with open(tmp_path / ".env", "w") as dotenv:
        dotenv.write(env)

    with chdir(tmp_path):
        settings = type("S", (DummySettings,), {})()
        assert settings.field_int_range == v


def test_validate_assignment() -> None:
    settings = DummySettings()
    with pytest.raises(ValidationError):
        settings.field_bool = 2  # type: ignore[assignment]
    with pytest.raises(ValidationError):
        settings.field_int_range = -1


def test_override() -> None:
    settings = DummySettings()
    with settings.override(field_bool=True):
        assert settings.field_bool is True
    assert settings.field_bool is False


def test_override_error() -> None:
    settings = DummySettings()
    with pytest.raises(ValidationError):
        with settings.override(field_int_range=3, field_int=1.1):
            pass
    assert settings.field_int == 42
    assert settings.field_int_range == 1


@pytest.mark.parametrize("temp", [True, False], ids=["temporary", "permanent"])
def test_reset(temp: bool) -> None:
    settings = DummySettings()
    default = settings.field_bool
    settings.field_bool = not default
    undo_reset = settings.reset("field_bool")
    with undo_reset if temp else nullcontext():
        assert settings.field_bool is default
    assert settings.field_bool is (not default if temp else default)


def test_reset_signature() -> None:
    settings = DummySettings()
    sig = inspect.signature(settings.reset)
    names_param = sig.parameters["names"]
    assert get_origin(names_param.annotation) is Literal
    assert get_args(names_param.annotation) == ("field_bool", "field_int", "field_int_range")


@pytest.mark.skipif(sys.version_info < (3, 14), reason="requires annotationlib")
def test_reset_annotations() -> None:
    from contextlib import AbstractContextManager

    import annotationlib

    settings = DummySettings()

    assert annotationlib.get_annotations(settings.reset) == {
        "names": Literal["field_bool", "field_int", "field_int_range"],
        "return": AbstractContextManager[frozenset[Literal["field_bool", "field_int", "field_int_range"]]],
    }
