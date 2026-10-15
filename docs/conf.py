# Configuration file for the Sphinx documentation builder.

# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/page/usage/configuration.html

# -- Path setup --------------------------------------------------------------
import shutil
import sys
from datetime import datetime
from importlib.metadata import metadata
from pathlib import Path

from scverse_doc.registry import intersphinx
from sphinxcontrib import katex


HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "sphinx_ext_examples"))


# -- Project information -----------------------------------------------------

# NOTE: If you installed your project in editable mode, this might be stale.
#       If this is the case, reinstall it to refresh the metadata
info = metadata("scverse-misc")
project = info["Name"]
author = info["Author"]
copyright = f"{datetime.now():%Y}, {author}."
version = info["Version"]
urls = dict(pu.split(", ") for pu in info.get_all("Project-URL") or ())
repository_url = urls["Source"]

# The full version, including alpha/beta/rc tags
release = info["Version"]

bibtex_bibfiles = ["references.bib"]

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings.
# They can be extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
templates_path = ["_templates"]
extensions = [
    "scverse_doc",
    "sphinxcontrib.bibtex",
    "sphinxcontrib.katex",
    "sphinx_autodoc_typehints",
    "sphinx_codeautolink",
    "IPython.sphinxext.ipython_console_highlighting",
    "scverse_misc.sphinx_ext",
]

source_repository = repository_url
napoleon_google_docstring = True
napoleon_numpy_docstring = False
typehints_defaults = "braces"
always_use_bars_union = True  # use `|` instead of `Union` in types even when building with Python ≤3.14

intersphinx_mapping = intersphinx() | {
    "scanpy": ("https://scanpy.readthedocs.io/en/stable/", None),
    "pooch": ("https://www.fatiando.org/pooch/latest/", None),
    "pydantic": ("https://pydantic.dev/docs/validation/", None),
}

html_static_path = ["_static"]
html_css_files = ["css/custom.css"]

katex_prerender = shutil.which(katex.NODEJS_BINARY) is not None

nitpick_ignore: list[tuple[str, str]] = [
    # If building the documentation fails because of a missing link that is outside your control,
    # you can add an exception to this list.
    ("py:class", "scverse_misc._deprecated.CallableWithDeprecatedArg"),
]
