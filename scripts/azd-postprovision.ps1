[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Update-LocalEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $lines = @(if (Test-Path -Path $Path) { Get-Content -Path $Path } else { @() })
    $updated = $false

    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^$([regex]::Escape($Key))=") {
            $lines[$index] = "$Key=$Value"
            $updated = $true
        }
    }

    if (-not $updated) {
        if ($lines.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($lines[-1])) {
            $lines += ""
        }
        $lines += "# Azure deployment output (managed by azd postprovision)"
        $lines += "$Key=$Value"
    }

    Set-Content -Path $Path -Value $lines -Encoding UTF8
}

$serviceUri = (azd env get-value SERVICE_MCP_URI 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($serviceUri)) {
    throw "SERVICE_MCP_URI was not available after provisioning."
}

$mcpServerUrl = "$($serviceUri.TrimEnd('/'))/mcp"
azd env set MCP_SERVER_URL $mcpServerUrl | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not persist MCP_SERVER_URL in the active azd environment."
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Update-LocalEnvValue -Path (Join-Path $repositoryRoot ".env") -Key "MCP_SERVER_URL" -Value $mcpServerUrl
Write-Host "Updated MCP_SERVER_URL in the active azd environment and root .env."