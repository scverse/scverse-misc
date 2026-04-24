from __future__ import annotations

import textwrap
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from types import GenericAlias
from typing import Literal

import dotenv
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from ._utils import copy_func


def _type_str(field: FieldInfo) -> str:
    return (
        field.annotation.__name__
        if isinstance(field.annotation, type) and not isinstance(field.annotation, GenericAlias)
        else str(field.annotation)
    )


_docstring_template = """Allows users to customize settings for the `{package}` package.

Settings here will generally be for advanced use-cases and should be used with caution.

For setting an option use :func:`~{package}.{name}.override` (local) or set the attributes directly (global)
i.e., `{package}.{name}.my_setting = foo`. For assignment by environment variable, use the variable name in
all caps with `{env_prefix}` as the prefix before import of `{package}`.
"""


class Settings(BaseSettings):
    '''Base class for package settings.

    This class can be subclassed by individual packages to get package-specific settings handling.
    Settings will be validated on assignment thanks to Pydantic. The class requires one argument
    `exported_object_name` and one optional argument `docstring_style`, which will be used to construct
    a suitable docstring (see the examples).

    Both a settings instance and its `override` method should be added to the package documentation.

    Thanks to Pydantic Settings, settings values will also be loaded from environment variables or `.env`
    files. Environment variables must be prefixex with `$PACKAGE_NAME_` to take effect, where `$PACKAGE_NAME`
    is the name of the package of the subclass. This can be overridden by passing `env_prefix=CUSTOMPREFIX`
    as class argument.

    Examples:
        >>> from typing import Annotated
        ... from pydantic import Field
        ... from scverse_misc import Settings
        ...
        ...
        ... class MySettings(Settings, exported_object_name="settings", docstring_style="numpy"):
        ...     eps: Annotated[float, Field(gt=0, lt=1)] = 1e-8
        ...     """Small epsilon for numerical stability."""
        ...
        ...     use_optional_feature: bool = False
        ...     """Whether to use the optional feature."""
        ...
        ...
        ... settings = MySettings()
    '''

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings, dotenv_settings

    @staticmethod
    def _get_packagename(subcls: type[Settings]) -> str:
        package_name = subcls.__module__
        dotidx = package_name.find(".")
        if dotidx > -1:
            package_name = package_name[:dotidx]
        return package_name

    def __init_subclass__(subcls, *, exported_object_name: str, docstring_style: Literal["google", "numpy"] = "google"):
        if (config := subcls.__dict__.get("model_config")) is not None:
            if not config.get("validate_assignment", True):
                warnings.warn("`validate_assignment=False` is not supported, overriding.", RuntimeWarning, stacklevel=2)
            if not config.get("use_attribute_docstrings", True):
                warnings.warn(
                    "`use_attribute_docstrings=False` is not supported, overriding.", RuntimeWarning, stacklevel=2
                )
            if config.get("env_file") is not None:
                warnings.warn(
                    "Setting a custom env_file location is not supported, overriding.", RuntimeWarning, stacklevel=2
                )
        else:
            config = SettingsConfigDict()

        config["validate_assignment"] = True
        config["use_attribute_docstrings"] = True
        config["env_file"] = dotenv.find_dotenv()

        if not config.get("env_prefix"):
            config["env_prefix"] = f"{__class__._get_packagename(subcls)}_"  # type: ignore[name-defined] # https://github.com/python/mypy/issues/4177
        subcls.model_config = config

        super().__init_subclass__()

    @contextmanager
    def override(self, **kwargs: object) -> Generator[None]:
        """Context manager for local setting overrides.

        Subclasses will get a version with a docstring detailing the available parameters.
        """
        oldsettings = {argname: getattr(self, argname) for argname in kwargs.keys()}
        try:
            for argname, argval in kwargs.items():
                setattr(self, argname, argval)
            yield
        finally:
            for argname, argval in reversed(oldsettings.items()):
                setattr(self, argname, argval)

    @classmethod
    def __pydantic_init_subclass__(  # type: ignore[override]
        subcls, *, exported_object_name: str, docstring_style: Literal["google", "numpy"] = "google"
    ) -> None:
        subcls.__doc__ = (
            _docstring_template.format(
                package=__class__._get_packagename(subcls),  # type: ignore[name-defined] # https://github.com/python/mypy/issues/4177
                name=exported_object_name,
                env_prefix=subcls.model_config["env_prefix"].upper(),
            )
            + "\n\nThe following options are available:\n"
        )
        override_doc = "Provides local override via keyword arguments as a context manager.\n\n"
        if docstring_style == "google":
            override_doc += "Args:\n"
        else:
            override_doc += "Parameters\n----------\n"
        for fname, field in subcls.model_fields.items():
            subcls.__doc__ += f"""
.. attribute:: {exported_object_name}.{fname}
   :type: {_type_str(field)}
   :value: {field.default!r}\n"""

            description = f"(default `{field.default!r}`) "
            if field.description is not None:
                subcls.__doc__ += f"\n{textwrap.indent(field.description, '   ')}\n"
                description += field.description

            if docstring_style == "google":
                override_doc += f"""    {fname} ({_type_str(field)}): {textwrap.indent(description, "        ")}\n"""
            else:
                override_doc += f"""
{fname} : {_type_str(field)}
{textwrap.indent(description, "    ")}\n"""

        subcls.override = copy_func(  # type: ignore[method-assign,type-var]
            subcls.override,
            __doc__=override_doc,
            __module__=subcls.__module__,
            __qualname__=f"{subcls.__qualname__}.override",
        )
