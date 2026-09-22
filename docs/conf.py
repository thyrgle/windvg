"""Sphinx configuration for the windvg documentation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

project = "windvg"
author = "Christopher Sumnicht"
copyright = "2026, Christopher Sumnicht"  # noqa: A001
release = "0.1.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

exclude_patterns = ["_build", "**.ipynb_checkpoints"]
language = "en"

html_theme = "furo"
html_title = "windvg"

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

autodoc_member_order = "bysource"
