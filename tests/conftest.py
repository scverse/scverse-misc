from __future__ import annotations

from collections.abc import Callable
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import pytest

if TYPE_CHECKING:
    from sphinx.ext.napoleon.docstring import GoogleDocstring, NumpyDocstring
    from sphinx.testing.util import SphinxTestApp

if find_spec("sphinx"):
    pytest_plugins = ["sphinx.testing.fixtures"]


@pytest.fixture(scope="session", params=["google", "numpy"])
def docstring_style(request: pytest.FixtureRequest) -> Literal["google", "numpy"]:
    return cast(Literal["google", "numpy"], request.param)


@pytest.fixture(scope="session")
def parser(docstring_style: Literal["google", "numpy"]) -> type[GoogleDocstring | NumpyDocstring]:
    from sphinx.ext.napoleon.docstring import GoogleDocstring, NumpyDocstring

    return GoogleDocstring if docstring_style == "google" else NumpyDocstring


@pytest.fixture
def app(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp], docstring_style: Literal["google", "numpy"]
) -> SphinxTestApp:
    """Since we need the same set everywhere, we use this instead of static roots like `@pytest.mark.sphinx('html', testroot="mybook")`."""

    (tmp_path / "conf.py").write_text("")

    app = make_app(
        srcdir=tmp_path,
        confoverrides=dict(
            extensions=["sphinx.ext.autodoc", "scverse_misc.sphinx_ext", "sphinx.ext.napoleon"],
            typehints_defaults="braces",
            napoleon_google_docstring=docstring_style == "google",
            napoleon_numpy_docstring=docstring_style == "numpy",
        ),
    )

    return app
