@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set UV_CACHE_DIR=.uv-cache
uv run python -m src.tui.control_tui %*
