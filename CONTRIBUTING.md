# Contributing Guidelines

Thanks for considering contributing to this project!

These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Getting set up

You need [`uv`](https://docs.astral.sh/uv/), which installs Python 3.15 and every dependency for you. [`just`](https://just.systems) is optional: each recipe in the `justfile` is a plain command you can run yourself.

```text
git clone https://github.com/ivanlonel/steam-manager
cd steam-manager
just bootstrap        # or: uv sync --locked && uv run prek install --overwrite
```

## Git hooks

Quality checks run as git hooks managed by [prek](https://github.com/j178/prek), a drop-in replacement for pre-commit. `just bootstrap` installs them. To run every hook against the whole tree:

```text
just prek             # or: uv run prek run --all-files
```

prek only checks tracked files, so `git add` new files first. The hook configuration lives in `.pre-commit-config.yaml`.

## Code style and checks

- **Formatting and linting**: [`ruff`](https://docs.astral.sh/ruff/) with every rule selected, plus [`flake8`](https://flake8.pycqa.org/) and [`pylint`](https://www.pylint.org/).
- **Type checking**: [`mypy`](https://mypy-lang.org/) in strict mode and [`ty`](https://docs.astral.sh/ty/). Everything is annotated, tests included.
- **Docstrings**: Sphinx style, without `:type:` or `:rtype:` fields.
- **Dependencies**: [`deptry`](https://deptry.com/) fails on an unused or undeclared one.

The detailed rules are in [`CLAUDE.md`](CLAUDE.md), and the project's vocabulary is in [`GLOSSARY.md`](GLOSSARY.md).

## Tests

Code is written test-first: a change comes with a test that failed before it.

```text
just test             # or: uv run pytest
just test -k version  # arguments go to pytest
```

Branch coverage must stay at or above 90%. Tests that talk to Steam or HowLongToBeat carry the `live` marker and never run unless asked for with `-m live`.

## Pull requests

- Run `just check` before opening one; it is what CI runs.
- Keep each pull request self-contained and, where possible, under 150,000 diff characters.
- Don't open drafts: the automated reviewer skips them.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). Pull requests are merged by rebase.
