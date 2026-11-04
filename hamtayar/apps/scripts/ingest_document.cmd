@echo off
setlocal
cd /d "%~dp0..\.."
uv run python -m apps.document_ingestion.cli %*
exit /b %ERRORLEVEL%
