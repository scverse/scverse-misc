from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

import pytest
from sphinx.testing.util import SphinxTestApp

pytest_plugins = ["sphinx.testing.fixtures"]


@pytest.fixture(scope="session", params=["google", "numpy"])
def docstring_style(request: pytest.FixtureRequest) -> Literal["google", "numpy"]:
    return cast(Literal["google", "numpy"], request.param)


@pytest.fixture
def app(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp], docstring_style: Literal["google", "numpy"]
) -> SphinxTestApp:
    """Since we need the same set everywhere, we use this instead of static roots like `@pytest.mark.sphinx('html', testroot="mybook")`."""

    (tmp_path / "conf.py").write_text("")

    app = make_app(
        srcdir=tmp_path,
        confoverrides=dict(
            extensions=[
                "sphinx.ext.autodoc",
                "scverse_misc.sphinx_ext",
                "sphinx.ext.napoleon",
                "sphinx_autodoc_typehints",
            ],
            typehints_defaults="braces",
            napoleon_google_docstring=docstring_style == "google",
            napoleon_numpy_docstring=docstring_style == "numpy",
        ),
    )

    return app
