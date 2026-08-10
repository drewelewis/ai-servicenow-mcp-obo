[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-AzdEnvironmentValues {
    $values = @{}
    if (-not [string]::IsNullOrWhiteSpace($env:AZURE_ENV_NAME)) {
        foreach ($entry in Get-ChildItem Env:) {
            $values[$entry.Name] = $entry.Value
        }
        return $values
    }

    $rawValues = azd env get-values
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read the active azd environment."
    }

    foreach ($line in $rawValues) {
        if ($line -match '^([^=]+)=(.*)$') {
            $values[$matches[1]] = $matches[2].Trim().Trim('"')
        }
    }

    return $values
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI is required for Entra provisioning. Install it from https://aka.ms/azure-cli."
}

if (-not (Get-Command azd -ErrorAction SilentlyContinue)) {
    throw "Azure Developer CLI is required. Install it from https://aka.ms/azd."
}

$azdValues = Get-AzdEnvironmentValues
$subscriptionId = $azdValues["AZURE_SUBSCRIPTION_ID"]
if ([string]::IsNullOrWhiteSpace($subscriptionId)) {
    throw "AZURE_SUBSCRIPTION_ID is not set in the active azd environment."
}

$configuredTenantId = $azdValues["SERVICENOW_SN_JWT_TENANT_ID"]
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
az account show --output none 2>$null
$accountShowExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
if ($accountShowExitCode -ne 0) {
    Write-Host "Azure CLI authentication is required for Microsoft Graph provisioning."
    $env:AZURE_CORE_LOGIN_EXPERIENCE_V2 = "off"
    $loginArguments = @("login", "--output", "none")
    if (-not [string]::IsNullOrWhiteSpace($configuredTenantId)) {
        $loginArguments += @("--tenant", $configuredTenantId)
    }

    az @loginArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI login failed."
    }
}

az account set --subscription $subscriptionId
if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI could not select the azd subscription."
}

$tenantId = az account show --query tenantId --output tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($tenantId)) {
    throw "Azure CLI could not resolve the tenant for the azd subscription."
}

$bootstrapParameters = @{
    TenantId = $tenantId
    ConfigureAzdEnvironment = $true
}

if ($azdValues.ContainsKey("COPILOT_STUDIO_REDIRECT_URI")) {
    $bootstrapParameters["CopilotStudioRedirectUri"] = $azdValues["COPILOT_STUDIO_REDIRECT_URI"]
}

Write-Host "Provisioning Entra applications for the active azd environment."
& (Join-Path $PSScriptRoot "bootstrap-entra-obo.ps1") @bootstrapParameters