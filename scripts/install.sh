#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
export npm_config_cache="${npm_config_cache:-$PWD/.cache/npm}"
command -v tesseract >/dev/null || { echo 'Install tesseract-ocr and fonts-noto-cjk using your OS package manager first.'; exit 1; }
command -v uv >/dev/null || { echo 'Install uv (https://docs.astral.sh/uv/) first.'; exit 1; }
test -d .venv || uv venv --python python3 .venv
uv pip install --python .venv/bin/python -r backend/requirements.lock
uv pip install --python .venv/bin/python 'torch==2.14.1' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python scripts/init_env.py
.venv/bin/python scripts/download_models.py
(cd frontend && npm ci && npm run build)
