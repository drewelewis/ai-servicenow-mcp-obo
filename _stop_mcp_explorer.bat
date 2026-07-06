@echo off
setlocal

REM Run from repository root (folder containing this script)
cd /d "%~dp0"

echo Looking for MCP Explorer and server processes...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^(node|python|python3|py)\.exe$') -and ($_.CommandLine -match '@modelcontextprotocol/inspector|servicenow-mcp\.py|mcp_server_servicenow\.cli') }; if (-not $procs) { Write-Host 'No matching MCP Explorer processes were found.'; exit 0 }; foreach ($p in $procs) { Write-Host ('Stopping PID {0} ({1})...' -f $p.ProcessId, $p.Name); Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host 'Done. MCP Explorer related processes were stopped.'"

endlocal
