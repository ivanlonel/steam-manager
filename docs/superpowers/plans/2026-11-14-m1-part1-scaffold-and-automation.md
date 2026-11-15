# Milestone 1, part 1: scaffold, gates and automation: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A repository where every later pull request is linted, type-checked, tested on three
platforms and documented automatically, before any feature code exists.

**Architecture:** A `src/`-layout package built with `uv_build`, quality gates run by prek
locally and in GitHub Actions, Sphinx docs published to GitHub Pages, Renovate keeping pins
current. Two pull requests: PR 1 (`build/scaffold`) and PR 2 (`docs/design`).

**Tech Stack:** Python 3.15, uv, prek, ruff, flake8, pylint, mypy, ty, deptry, pytest,
hypothesis, Sphinx + MyST, GitHub Actions, Renovate, just.

**Spec:** `docs/superpowers/specs/2026-11-14-steam-manager-design.md`

## Global Constraints

- Python `>=3.15`. Lines up to 99 characters. Complete typing, tests and scripts included.
- Sphinx-style docstrings without `:type:` or `:rtype:`.
- pytest `~=9.2`, pytest-cov `~=7.1`, hypothesis `~=6.170`. Coverage `fail_under = 90`, branch.
- Every suppression comment (`# noqa`, `# type: ignore`, `# ty: ignore`, `# pylint: disable`,
  `# pragma: no cover`) carries its reason.
- A runtime dependency is declared in the pull request that first imports it (deptry enforces
  this), never earlier.
- The application never depends on `just`.
- Commits follow Conventional Commits. Pull requests are never drafts, are checked locally
  first, stay under 150,000 diff characters where possible, and merge by rebase.
- MIT license; author listed by name only.

## Review Focus

- A contributor on Linux or macOS without PowerShell runs `just check`: every recipe works in
  `sh` as well as `pwsh`. Pinned by Task 4's verification on the CI runners.
- A hook that matches no file passes silently and guards nothing: `check-hooks-apply` is
  enabled, and each hook is added in the pull request that brings its first file (Task 3, 7).
- A test file named `foo_test.py` would never be collected: `name-tests-test --pytest-test-first` is enabled (Task 3).
- A linter running on an older Python cannot parse 3.15-only syntax: hook environments use
  `python3.15` and Task 2 probes each tool with a `lazy import` statement.
- A network test slipping into CI: the `live` marker is deselected by default (Task 2).

## File Structure

PR 1:

- `pyproject.toml`: project metadata, dependency groups, every tool's configuration.
- `uv.lock`, `.python-version` (`3.15`).
- `src/steam_manager/__init__.py`: package docstring and `__version__`.
- `src/steam_manager/py.typed`: marks the package as typed.
- `tests/__init__.py`, `tests/steam_manager/__init__.py`, `tests/steam_manager/test___init__.py`.
- `.editorconfig`, `.gitattributes`, `.flake8`, `.mdformat.toml`, `.pre-commit-config.yaml`.
- `justfile`.
- `CLAUDE.md` (rules for coding agents), `CONTRIBUTING.md`, `CHANGELOG.md`.
- `.github/workflows/linting.yml`, `.github/workflows/testing.yml`, `.github/zizmor.yml`.

PR 2:

- `docs/conf.py`, `docs/index.md`, `docs/development/*.md`, `docs/reference/*.md`.
- `GLOSSARY.md`, `docs/adr/*.md`, `docs/superpowers/**` (already written).
- `.github/workflows/documentation.yml`, `update-dependencies.yml`, `auto-labeler.yml`,
  `release.yml` (workflow), `.github/release.yml` (release-notes categories),
  `.github/labeler.yml`, `.github/renovate.json`, `.github/ISSUE_TEMPLATE/*.yml`.

______________________________________________________________________

### Task 1: Package skeleton

**Files:**

- Create: `pyproject.toml`, `.python-version`, `src/steam_manager/__init__.py`,
  `src/steam_manager/py.typed`, `tests/__init__.py`, `tests/steam_manager/__init__.py`
- Test: `tests/steam_manager/test___init__.py`

**Interfaces:**

- Produces: `steam_manager.__version__: Final[str]`, read with
  `importlib.metadata.version("steam-manager")`.

- [ ] **Step 1: Write `pyproject.toml` with metadata only**

`build-backend = "uv_build"`; `name = "steam-manager"`; `version = "0.1.0"`;
`requires-python = ">=3.15"`; `license = "MIT"`; classifiers include
`"Private :: Do Not Upload"` (releases are GitHub-only); `dependencies = []`; groups
`test = ["hypothesis~=6.170.15", "pytest~=9.2.0", "pytest-cov~=7.1.0"]`.

- [ ] **Step 2: Write the failing test**

```python
def test_version_matches_the_installed_metadata() -> None:
    assert steam_manager.__version__ == importlib.metadata.version("steam-manager")


def test_version_is_a_release_number() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", steam_manager.__version__)
```

- [ ] **Step 3: Run it and see it fail**

Run: `uv run pytest tests/steam_manager/test___init__.py`
Expected: FAIL with `AttributeError: module 'steam_manager' has no attribute '__version__'`

- [ ] **Step 4: Implement `__version__` in `src/steam_manager/__init__.py`**

- [ ] **Step 5: Run it and see it pass**, then commit `build: add the package skeleton`

### Task 2: Tool configuration

**Files:**

- Modify: `pyproject.toml`

- Create: `.flake8`, `.editorconfig`, `.gitattributes`, `.mdformat.toml`

- [ ] **Step 1: Add the `dev`, `type` and `hook` groups**

`dev`: deptry, flake8, flake8-cognitive-complexity, flake8-rst-docstrings, prek,
pydoclint[flake8], pylint, ruff, plus `test` and `type`. `type`: mypy[faster-cache], ty.
`hook`: packages used only as hooks so sync-with-uv can pin them from `uv.lock`
(editorconfig-checker, mdformat and its plugins, pre-commit-hooks, pyproject-fmt, sync-with-uv,
taplo, typos, uv, zizmor). All pinned `~=` to the versions current on 2026-11-14.

- [ ] **Step 2: Configure the tools as `stratified-packager` does, minus QGIS**

ruff (`select = ["ALL"]`, ignore COM812, CPY001, D203, D212; `line-length = 99`;
`docstring-code-format`; tests ignore PLR2004 and S101; `mccabe.max-complexity = 12`;
`pylint.max-args = 10`), pylint (same "governed by" disables), mypy (same strict flags and
`enable_error_code` list), ty (`respect-type-ignore-comments = false`), deptry, pytest
(`strict = true`, `minversion = "9.2"`, `addopts` with `--cov=steam_manager` and
`-m "not live"`, marker `live`), coverage (`branch`, `fail_under = 90`, `show_missing`).
`.flake8` carries flake8-rst-docstrings roles and pydoclint's Sphinx settings.

- [ ] **Step 3: Verify every tool runs clean on Python 3.15**

Run: `uv run ruff check`, `uv run ruff format --check`, `uv run flake8`, `uv run pylint src tests`, `uv run mypy .`, `uv run ty check`, `uv run deptry .`, `uv run pytest`
Expected: each exits 0; pytest reports 100% coverage.

- [ ] **Step 4: Probe 3.15-only syntax**

Put `lazy import json` in a scratch module under `src/steam_manager/`, rerun Step 3, and record
in `CLAUDE.md` which tools reject it (if any does, the construct is banned until it parses).
Delete the scratch module.

- [ ] **Step 5: Commit** `build: configure the linters, type checkers and test runner`

### Task 3: Git hooks

**Files:**

- Create: `.pre-commit-config.yaml`

- Modify: `pyproject.toml` (`[tool.sync-with-uv]`)

- [ ] **Step 1: Write the hook configuration**

Hook environments use `python3.15`. Hooks in PR 1: meta (`check-hooks-apply`,
`check-useless-excludes`); prek builtin file hygiene; pre-commit-hooks (`check-ast`,
`debug-statements`, `name-tests-test --pytest-test-first`); editorconfig-checker; typos;
gitleaks; pygrep hooks; uv-lock; uv-sync (`--locked`); sync-with-uv; pyproject-fmt; taplo (other
TOML files); ruff-check `--fix` and ruff-format; flake8 and pylint with their plugins pinned
through `# sync-with-uv`; local `ty`, `mypy`, `deptry` (`uv run --exact`), `just --fmt --check`; mdformat with plugins; actionlint; zizmor.

- [ ] **Step 2: Verify**

Run: `git add -A; uv run prek run --all-files`
Expected: every hook passes or reports "Passed"; none reports "no files to check".

- [ ] **Step 3: Commit** `build: add the git hooks`

### Task 4: Task runner

**Files:**

- Create: `justfile`

- [ ] **Step 1: Write recipes that run unchanged in `sh` and `pwsh`**

Groups and recipes: setup (`bootstrap`, `sync`, `lock`, `hooks`), qa (`format`, `lint`,
`type-check`, `prek`, `check`), test (`test *args`, `cov-serve`), clean (`clean`). `check` is
exactly what CI runs: `prek`, then `test`.

- [ ] **Step 2: Verify**

Run: `just --fmt --check --unstable; just check`
Expected: exit 0.

- [ ] **Step 3: Commit** `build: add the justfile`

### Task 5: Contributor documents

**Files:**

- Create: `CLAUDE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`

- Modify: `README.md`

- [ ] **Step 1: Write them**

`CLAUDE.md`: project summary, pointers to the spec, glossary and ADRs, the rules from *Global
Constraints*, the non-QGIS rules of `stratified-packager/CLAUDE.md` (pathlib only, no global
mutable state, tests mirror the source tree, typing and docstring style, English only), the
pull-request workflow, and the commands. `CHANGELOG.md` in Keep a Changelog form with an
`Unreleased` section.

- [ ] **Step 2: Verify** with `uv run prek run --all-files`, then commit
  `docs: add the contributor guides and changelog`

### Task 6: Linting and testing workflows

**Files:**

- Create: `.github/workflows/linting.yml`, `.github/workflows/testing.yml`,
  `.github/zizmor.yml`

- [ ] **Step 1: Write the workflows**

Actions pinned by commit SHA with a version comment. `linting`: checkout, setup-uv with Python
3.15, prek-action `--all-files`. `testing`: matrix `ubuntu-latest`, `windows-latest`,
`macos-latest`; `uv run --no-dev --group test pytest` writing JUnit and coverage XML, uploaded
as artifacts. Both: `permissions: contents: read`, `persist-credentials: false`, concurrency
that cancels superseded runs.

- [ ] **Step 2: Verify locally** with `uv run prek run --all-files` (actionlint, zizmor)

- [ ] **Step 3: Commit, push, open the pull request**

Check the size first: `git diff main...HEAD | Measure-Object -Character`. Then
`gh pr create --base main` (not a draft). Expected: both workflows green on all runners.

### Task 7: Documentation site and repository automation (PR 2)

**Files:**

- Create: the PR 2 files listed under *File Structure*

- Modify: `pyproject.toml` (`doc` group), `.pre-commit-config.yaml` (hooks that now have
  files: `check-json`, `check-jsonc`, `renovate-config-validator`), `justfile` (`docs`,
  `docs-live`), `.flake8` / ruff per-file ignores for `docs/conf.py`

- [ ] **Step 1: Sphinx skeleton**

`doc` group: sphinx, myst-parser[linkify], sphinx-autodoc-typehints, sphinx-copybutton,
sphinx-rtd-theme, sphinx-autobuild. `docs/conf.py` typed like the reference one, `nitpicky`,
intersphinx to Python; pages: index, development (environment, testing, pull requests),
reference (glossary and ADRs included from their files), API (autosummary).

Run: `uv run --group doc sphinx-build -M html docs docs/_build -j auto -W --keep-going`
Expected: build succeeds with no warnings.

- [ ] **Step 2: Workflows and Renovate**

`documentation` (build on every pull request; deploy to Pages on `main`), `update-dependencies`
(post-Renovate sync-with-uv and pyproject-fmt, needs the `RENOVATE_TOKEN` secret),
`auto-labeler`, `release` (a tag builds with `uv build` and creates a GitHub Release with the
wheel and sdist). `renovate.json` as in `stratified-packager` without the QGIS manager, with
`constraints.python = "3.15"` and `automergeStrategy = "rebase"`.

- [ ] **Step 3: Verify** with `just check` and the docs build, then commit, push and open the
  pull request as in Task 6.
