# CLAUDE.md

Guidance for coding agents working in this repository.

## Project

steam-manager is a command-line and local web application that gathers one Steam account's store and account data into a per-profile SQLite database, and helps its owner manage that account. It is public and must work for any Steam user: nothing about one person's account, country or files is built in.

- **Design**: `docs/superpowers/specs/2026-11-14-steam-manager-design.md`. It is normative: read it before changing behaviour, and amend it in the same change that alters behaviour.
- **Vocabulary**: `GLOSSARY.md`. Use its terms in code, docs and messages, and never the ones it lists under *Avoid*.
- **Decisions**: `docs/adr/`. Read them before "fixing" something that looks odd.
- **Plans**: `docs/superpowers/plans/`, one per stage of a milestone.

Runtime is Python 3.15+. Dependencies via **uv** (`pyproject.toml`, `uv.lock`); git hooks via **prek** (`.pre-commit-config.yaml`); common tasks via **just**, which is optional: every recipe is a plain `uv run` command.

## Layout

- `src/steam_manager/`: the package. Sources only write raw answers to the raw archive; one loader turns archived answers into database rows (ADR 0002).
- `tests/`: mirrors `src/` one to one. Every module `src/steam_manager/a/b.py` has `tests/steam_manager/a/test_b.py`.
- `docs/`: Sphinx site, ADRs, design and plans.

## Rules (MUST)

1. **Test first.** No production code without a test that was seen failing first. Use the `superpowers:test-driven-development` skill.
1. **Secrets never leak.** No token, key, cookie or URL query string in a log line, an exception message, an export or the repository. Raise errors that name the endpoint, never the full URL.
1. **Private data stays private.** Profile data lives outside the repository. Test fixtures recorded from Steam are sanitized of account data before they are committed.
1. **Report, don't drop.** A field a source sends that no model declares is counted and reported, never silently discarded.
1. **Typing.** Annotate everything, tests and scripts included, except obviously-typed locals. Parameters take abstract types (`Iterable`, `Mapping`, `Sequence`); return types are specific. Use `@override`, `Final`, `ClassVar`, `Protocol` and `TypedDict` where they fit, and `if TYPE_CHECKING:` for checker-only imports.
1. **Docstrings** are Sphinx style: `:param:`, `:return:` (when not `None`), `:yield:`, `:raise:` (one per known exception). Never `:type:` or `:rtype:`; the types are in the signature. The first line is a summary of at most 99 characters ending in a period, imperative for callables. Attributes get their own docstring.
1. **Suppression comments** (`# noqa`, `# type: ignore`, `# ty: ignore`, `# pylint: disable`, `# pragma: no cover`) always name the rule and carry a reason.
1. **Paths** are `pathlib.Path`, never `os.path` or string concatenation.
1. **No global mutable state.** Pass configuration as arguments.
1. **Dependencies** are declared by the change that first imports them; deptry fails on an unused or undeclared one.
1. **English only** in identifiers, literals, docstrings, comments and file names.
1. **Verify, don't trust.** Before relying on a remembered fact about an API or a library, look it up again. The Steam endpoints are undocumented and change.
1. **Commit messages** follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): `<type>[scope][!]: <description>`, imperative, at most 72 characters, no trailing period, with a body that says why.

## Style (SHOULD)

- Lines up to 99 characters. Prefer f-strings, except in logging calls, which use `%`-style deferred interpolation.
- Fail fast instead of guessing: an unexpected answer from a source is an error to report, not a value to paper over.
- The laziest solution that works: the standard library before a dependency, no abstraction with a single implementation, no code for a need that has not arrived.
- Python 3.15 syntax is welcome. Every tool in the gate parses `lazy import` and unpacking in comprehensions (checked 2026-11-14).

## Pull requests

- Never open a draft: the Sourcery reviewer skips drafts.
- Before opening one, run locally what CI runs: `just check`, and the docs build when docs changed.
- Keep each pull request self-contained, with CI able to pass, and under 150,000 diff characters when that is possible without an arbitrary cut (Sourcery does not review larger ones). Check with `git diff main...HEAD | wc -c`.
- Evaluate the reviewer's findings on their merits before merging. Merges are always by rebase.

## Commands

```text
just bootstrap     # uv sync --locked, then install the git hooks
just check         # everything CI checks: every hook, then the tests
just format        # ruff check --fix, ruff format
just lint          # ruff check, pylint src tests (flake8: `just prek flake8`)
just type-check    # ty check, mypy .
just test [args]   # uv run pytest [args]; network tests need `-m live`
just prek [hook]   # every hook on every file, or one hook
just docs          # Sphinx build of docs/, warnings are errors (what CI runs)
```

prek only checks tracked files: `git add` new files before running it.

## Known constraints

- pylint runs with `jobs = 1`: its parallel mode pickles with dill, and dill 0.4.1 fails on Python 3.15.
- Never install the `hook` dependency group into the project environment (`uv sync --group hook`, `uv run --group hook`). pydoclint needs `docstring-parser-fork` and cyclopts needs `docstring-parser`; both provide the module `docstring_parser`, and whichever is installed last breaks the other. That is also why flake8 and its plugins run as a hook with their own environment instead of through `uv run`.
- Hypothesis seeds `st.text` with the string literals of the imported source modules (not the test files). A property such as "a secret never appears in a message" therefore needs secrets that can't match source text: prefix them, as `tests/steam_manager/test_transport.py` does with `.map(lambda text: f"secret-{text}")`. Without it, a secret can be `api.steampowered.com`, which every error names.
- `PRAGMA foreign_keys` changes only outside a transaction. Python's sqlite3 opens one implicitly at the first INSERT, UPDATE or DELETE on a connection and keeps it until the commit; inside it the PRAGMA silently does nothing. Set it before any such statement, and read it back before relying on it, as `src/steam_manager/db/steam_schema.py` does: with foreign keys still on, dropping a table deletes its rows first and runs every `ON DELETE CASCADE` pointing at it.
- SQLAlchemy correlates a scalar subquery to the outer query, but not a subquery inside its FROM clause: one that names an outer alias gets that table added to its own FROM, a cross join that silently gathers every row's list into each one. The notebooks' `(SELECT json_group_array(x) FROM (SELECT … ORDER BY …))` is that shape. Order inside the aggregate instead, `aggregate_order_by(func.json_group_array(x), y)`, as `src/steam_manager/db/reports/store_columns.py` does.
- pylint infers that `func.coalesce(...)` returns `None` and flags its assignment (E1111, `assignment-from-no-return`). Call the `coalesce` class from `sqlalchemy.sql.functions` instead, which pylint reads correctly.
- `__all__` decides what the docs' recursive autosummary documents, and the docs build fails on every reference it can't resolve:
  - In a package, a submodule `__all__` leaves out gets no page, and every cross-reference into it fails. List the submodules, as `src/steam_manager/db/schema/__init__.py` and `src/steam_manager/loader/__init__.py` do.
  - In a module without `__all__`, imported names (Pydantic's `Field`, SQLAlchemy's `select`) are documented too, and their annotations don't resolve. Give every new module an `__all__` of its own names, as `src/steam_manager/archive.py` does.
  - A public type alias holding a Pydantic `AfterValidator` renders as a link to the validator, a private function. Validate in a `field_validator` instead, as `Settings` in `src/steam_manager/profiles.py` does.
- The ruff hook's autofix removes a `# noqa` it finds unused (RUF100) and leaves the reason after it in place. Delete that reason too.
