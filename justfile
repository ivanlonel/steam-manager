# Tasks for steam-manager: run `just` to list them. The application itself never needs just.
# Recipes run in sh, or in PowerShell on Windows, so they stick to plain commands.

set windows-shell := ["pwsh.exe", "-NoLogo", "-NoProfile", "-Command"]

export PYTHONUTF8 := "1"

[private]
default:
    @just --justfile {{ justfile() }} --list --unsorted

# Install the dependencies and the git hooks: everything a fresh clone needs
[group("setup")]
bootstrap: sync hooks

# Install the locked dependencies
[group("setup")]
sync:
    uv sync --locked

# Update uv.lock to the newest versions pyproject.toml allows
[group("setup")]
lock:
    uv lock --upgrade

# Run the git hooks on every commit
[group("setup")]
hooks:
    uv run prek install --overwrite

# Remove build, test and cache artifacts (keeps the virtual environment)
[group("setup")]
clean:
    uv run python -c "import pathlib, shutil; [shutil.rmtree(name, ignore_errors=True) for name in ('build', 'dist', 'htmlcov', 'junit', 'docs/_build', '.hypothesis', '.pytest_cache', '.mypy_cache', '.ruff_cache')]; [path.unlink() for path in pathlib.Path().glob('.coverage*')]"

# Fix what can be fixed automatically, then format
[group("qa")]
format:
    uv run ruff check --fix
    uv run ruff format

# Run the linters: ruff, flake8, pylint
[group("qa")]
lint:
    uv run ruff check
    uv run flake8
    uv run pylint src tests

# Run the type checkers: ty, mypy
[group("qa")]
type-check:
    uv run ty check
    uv run mypy .

# Run every git hook on every file, or only the named ones: `just prek mypy` (prek only sees tracked files: `git add` new ones first)
[group("qa")]
prek *hooks:
    uv run prek run --all-files {{ hooks }}

# Everything CI checks: every hook, then the tests
[group("qa")]
check: prek test

# Run the tests; arguments go to pytest: `just test -k version`
[group("test")]
test *args:
    uv run pytest {{ args }}

# Serve the HTML coverage report at http://localhost:PORT
[group("test")]
cov-serve port="8080":
    uv run python -m http.server --directory htmlcov {{ port }}
