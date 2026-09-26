$ErrorActionPreference = "Stop"
uv sync --extra dev --extra research
uv run adaptive-lad validate-configs
uv run pytest

