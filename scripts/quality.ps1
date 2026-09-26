$ErrorActionPreference = "Stop"
uv run ruff check .
uv run ruff format --check .
uv run mypy src/adaptive_lad
uv run adaptive-lad validate-configs
uv run pytest --cov=adaptive_lad --cov-report=term-missing
