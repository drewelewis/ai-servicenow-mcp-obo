@echo off
setlocal

REM Run from repository root (folder containing this script)
cd /d "%~dp0"

REM Ensure Node's npx is available
where npx >nul 2>&1
if errorlevel 1 (
	echo ERROR: npx was not found. Install Node.js and try again.
	exit /b 1
)

REM Activate local virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
	call ".venv\Scripts\activate.bat"
)

REM Start MCP Inspector in writable mode with no preset STDIO server.
REM Add the local or deployed /mcp URL as a Streamable HTTP connection in the UI.
npx -y @modelcontextprotocol/inspector %*

endlocal
