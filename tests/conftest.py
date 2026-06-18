from pathlib import Path
from typing import Literal, cast

import pytest

pytest_plugins = ["sphinx.testing.fixtures"]


@pytest.fixture(scope="session", params=["google", "numpy"])
def docstring_style(request: pytest.FixtureRequest) -> Literal["google", "numpy"]:
    return cast(Literal["google", "numpy"], request.param)


@pytest.fixture(scope="session")
def sphinx_test_tempdir(tmp_path_factory: pytest.TempPathFactory, docstring_style: Literal["google", "numpy"]) -> Path:
    """Since we need the same set everywhere, we use this instead of static roots like `@pytest.mark.sphinx('html', testroot="mybook")`."""
    sphinx_test_tempdir = tmp_path_factory.getbasetemp() / docstring_style
    p = sphinx_test_tempdir / "root" / "conf.py"
    p.parent.mkdir(parents=True)
    p.write_text(f"""
extensions = ["sphinx.ext.autodoc", "scverse_misc.sphinx_ext", "sphinx.ext.napoleon", "sphinx_autodoc_typehints"]
typehints_defaults = "braces"
napoleon_google_docstring = {docstring_style == "google"}
napoleon_numpy_docstring = {docstring_style == "numpy"}
""")
    return sphinx_test_tempdir
