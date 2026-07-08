[CmdletBinding()]
param(
    [string]$SourceEnvFile = ".env.obo.generated",
    [string]$TargetEnvFile = ".env",
    [bool]$CreateBackup = $true,
    [switch]$WhatIfOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-EnvMap {
    param([Parameter(Mandatory = $true)][string]$Path)

    $map = [ordered]@{}

    if (-not (Test-Path -Path $Path)) {
        return $map
    }

    $lines = Get-Content -Path $Path
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
        if ($trimmed.StartsWith("#")) { continue }

        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { continue }

        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1)
        $map[$key] = $value
    }

    return $map
}

if (-not (Test-Path -Path $SourceEnvFile)) {
    throw "Source env file not found: $SourceEnvFile"
}

$sourceMap = Read-EnvMap -Path $SourceEnvFile
if ($sourceMap.Count -eq 0) {
    throw "No key=value entries found in source env file: $SourceEnvFile"
}

$targetMap = Read-EnvMap -Path $TargetEnvFile

$keysToApply = @(
    "SERVICENOW_OBO_TENANT_ID",
    "SERVICENOW_OBO_CLIENT_ID",
    "SERVICENOW_OBO_CLIENT_SECRET",
    "SERVICENOW_OBO_SCOPE",
    "SERVICENOW_OBO_PUBLIC_CLIENT_ID",
    "SERVICENOW_OBO_USER_SCOPE",
    "SERVICENOW_OBO_TOKEN_ENDPOINT",
    "SERVICENOW_OBO_USER_ASSERTION",
    "SERVICENOW_SN_JWT_TENANT_ID",
    "SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID",
    "SERVICENOW_SN_JWT_CLIENT_ID",
    "SERVICENOW_SN_JWT_PRIVATE_KEY_PATH",
    "SERVICENOW_SN_JWT_CLIENT_SECRET",
    "SERVICENOW_SN_JWT_TOKEN_ENDPOINT",
    "SERVICENOW_SN_JWT_USER_CLAIM_SOURCE",
    "SERVICENOW_SN_JWT_SCOPE",
    "SERVICENOW_SN_JWT_KID",
    "SERVICENOW_SN_JWT_EXPECTED_AUDIENCE",
    "SERVICENOW_SN_JWT_EXPECTED_ISSUER",
    "SERVICENOW_SN_JWT_ASSERTION_TTL",
    "SERVICENOW_SN_JWT_CACHE_SAFETY_BUFFER",
    "SERVICENOW_SN_JWT_USER_ASSERTION",
    "SERVICENOW_SN_JWT_ALLOW_STATIC_ASSERTION"
)

$applied = New-Object System.Collections.Generic.List[string]
foreach ($key in $keysToApply) {
    if ($sourceMap.Contains($key)) {
        $targetMap[$key] = $sourceMap[$key]
        $applied.Add($key) | Out-Null
    }
}

if ($applied.Count -eq 0) {
    throw "No recognized SERVICENOW_OBO_* or SERVICENOW_SN_JWT_* keys found in source env file: $SourceEnvFile"
}

$newContent = @()
$newContent += "# Updated by scripts/apply-obo-env.ps1"
$newContent += "# Source: $SourceEnvFile"
foreach ($entry in $targetMap.GetEnumerator()) {
    $newContent += "$($entry.Key)=$($entry.Value)"
}

if ($WhatIfOnly) {
    Write-Host "WhatIfOnly enabled. No file was written."
    Write-Host "Keys that would be applied:"
    $applied | ForEach-Object { Write-Host " - $_" }
    return
}

if ((Test-Path -Path $TargetEnvFile) -and $CreateBackup) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = "$TargetEnvFile.bak-$timestamp"
    Copy-Item -Path $TargetEnvFile -Destination $backupPath -Force
    Write-Host "Backup created: $backupPath"
}

Set-Content -Path $TargetEnvFile -Value $newContent -Encoding UTF8

Write-Host "Applied generated auth settings to: $TargetEnvFile"
Write-Host "Keys applied:"
$applied | ForEach-Object { Write-Host " - $_" }
