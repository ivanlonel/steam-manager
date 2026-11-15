"""Configure the Sphinx documentation site."""

from importlib.metadata import version as installed_version
from typing import Final

project: Final[str] = "steam-manager"
author: Final[str] = "Ivan Donisete Lonel"
copyright: Final[str] = f"2026, {author}"  # noqa: A001  # Sphinx reads this exact name
release: Final[str] = installed_version(project)
version: Final[str] = release

extensions: Final[list[str]] = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_autodoc_typehints",  # after sphinx.ext.autodoc, whose output it post-processes
    "sphinx_copybutton",
    "sphinx_rtd_theme",
]
source_suffix: Final[dict[str, str]] = {".md": "markdown", ".rst": "restructuredtext"}
# The design and the plans are working documents for contributors, read on GitHub.
exclude_patterns: Final[list[str]] = ["_build", "superpowers"]

# Unresolved cross-references are warnings, and the build treats warnings as errors.
nitpicky: Final[bool] = True
# httpx documents itself with MkDocs, so there is no inventory to link its classes to.
# DeclarativeBase's attribute docstrings use SQLAlchemy's private shorthands (_orm., _schema.),
# which only its own documentation resolves.
nitpick_ignore_regex: Final[list[tuple[str, str]]] = [
    ("py:class", r"httpx\..*"),
    ("py:class", r"_(orm|schema)\..*"),
]
# SQLAlchemy builds each mapped class's __init__ inside sqlalchemy.orm.instrumentation, whose
# TYPE_CHECKING block uses relative imports that can't run outside that package.
suppress_warnings: Final[list[str]] = ["sphinx_autodoc_typehints.guarded_import"]


def typehints_fixup_module_name(module: str) -> str:
    """
    Name a module as its documentation does, so that links to its members resolve.

    :param module: Where a class is defined.
    :return: Where it is documented.
    """
    return "sqlalchemy.types" if module == "sqlalchemy.sql.type_api" else module



autodoc_default_options: Final[dict[str, bool]] = {"members": True, "undoc-members": True}
autodoc_member_order: Final[str] = "bysource"
autosummary_generate: Final[bool] = True
# Honour a module's __all__ where it has one (models/lookups.py keeps pydantic's names out).
autosummary_ignore_module_all: Final[bool] = False
intersphinx_mapping: Final[dict[str, tuple[str, None]]] = {
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "python": ("https://docs.python.org/3/", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/21/", None),
}

myst_enable_extensions: Final[list[str]] = ["colon_fence", "deflist", "linkify"]

copybutton_exclude: Final[str] = ".linenos, .go, .gp"

html_theme: Final[str] = "sphinx_rtd_theme"
