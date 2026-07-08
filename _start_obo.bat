@echo off
setlocal

REM Run from repository root (folder containing this script)
cd /d "%~dp0"

REM Activate local virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
	call ".venv\Scripts\activate.bat"
)

REM Launch interactive OBO helper from repo root
REM Pass through any extra args provided to this .bat file.
python scripts/interactive_mcp_client.py %*

endlocal
