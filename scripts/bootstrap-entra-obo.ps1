[CmdletBinding()]
param(
    [string]$TenantId,
    [string]$BrokerAppName = "servicenow-mcp-obo-broker",
    [string]$DownstreamApiAppName = "servicenow-mcp-obo-downstream-api",
    [string]$DownstreamScopeName = "user_impersonation",
    [string]$DownstreamIdentifierUri,
    [int]$SecretYears = 1,
    [string]$OutputEnvFile = ".env.obo.generated"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-AzCli {
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Azure CLI is required. Install it first: https://aka.ms/azure-cli"
    }
}

function Assert-AzLogin {
    try {
        az account show --output none 2>$null
    } catch {
        throw "You must sign in first. Run: az login"
    }
}

function Get-AppByDisplayName {
    param([Parameter(Mandatory = $true)][string]$DisplayName)

    $raw = az ad app list --display-name $DisplayName --query "[0]" --output json
    if ([string]::IsNullOrWhiteSpace($raw) -or $raw.Trim() -eq "null") {
        return $null
    }

    return ($raw | ConvertFrom-Json)
}

function Ensure-App {
    param([Parameter(Mandatory = $true)][string]$DisplayName)

    $app = Get-AppByDisplayName -DisplayName $DisplayName
    if ($null -ne $app) {
        Write-Host "Reusing existing app registration: $DisplayName ($($app.appId))"
        return $app
    }

    Write-Host "Creating app registration: $DisplayName"
    $created = az ad app create --display-name $DisplayName --sign-in-audience "AzureADMyOrg" --output json | ConvertFrom-Json
    return $created
}

function Ensure-ServicePrincipal {
    param([Parameter(Mandatory = $true)][string]$AppId)

    try {
        az ad sp show --id $AppId --output none 2>$null
        Write-Host "Service principal exists for appId: $AppId"
    } catch {
        Write-Host "Creating service principal for appId: $AppId"
        az ad sp create --id $AppId --output none
    }
}

function Configure-DownstreamApiScope {
    param(
        [Parameter(Mandatory = $true)]$App,
        [Parameter(Mandatory = $true)][string]$IdentifierUri,
        [Parameter(Mandatory = $true)][string]$ScopeName
    )

    $scopeId = [Guid]::NewGuid().ToString()
    $patchBody = @{
        identifierUris = @($IdentifierUri)
        api = @{
            requestedAccessTokenVersion = 2
            oauth2PermissionScopes = @(
                @{
                    id = $scopeId
                    value = $ScopeName
                    type = "User"
                    isEnabled = $true
                    adminConsentDisplayName = "Access $ScopeName"
                    adminConsentDescription = "Allow the app to access this API on behalf of the signed-in user."
                    userConsentDisplayName = "Access $ScopeName"
                    userConsentDescription = "Allow the app to access this API on your behalf."
                }
            )
        }
    } | ConvertTo-Json -Depth 10 -Compress

    Write-Host "Configuring downstream API scope '$ScopeName' on $IdentifierUri"
    az rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$($App.id)" --headers "Content-Type=application/json" --body $patchBody --output none

    return $scopeId
}

function Grant-DelegatedPermission {
    param(
        [Parameter(Mandatory = $true)][string]$BrokerAppId,
        [Parameter(Mandatory = $true)][string]$DownstreamAppId,
        [Parameter(Mandatory = $true)][string]$ScopeId
    )

    Write-Host "Granting delegated permission from broker to downstream API"
    az ad app permission add --id $BrokerAppId --api $DownstreamAppId --api-permissions "$ScopeId=Scope" --output none

    try {
        az ad app permission admin-consent --id $BrokerAppId --output none
        Write-Host "Admin consent granted for broker app."
    } catch {
        Write-Warning "Admin consent could not be granted automatically. A tenant admin may need to run: az ad app permission admin-consent --id $BrokerAppId"
    }
}

function Create-OrRotateBrokerSecret {
    param(
        [Parameter(Mandatory = $true)][string]$BrokerAppId,
        [Parameter(Mandatory = $true)][int]$Years
    )

    Write-Host "Creating new client secret for broker app"
    $cred = az ad app credential reset --id $BrokerAppId --append --display-name "servicenow-mcp-obo" --years $Years --output json | ConvertFrom-Json
    return $cred.password
}

Assert-AzCli
Assert-AzLogin

if ([string]::IsNullOrWhiteSpace($TenantId)) {
    $TenantId = az account show --query tenantId --output tsv
}

if ([string]::IsNullOrWhiteSpace($TenantId)) {
    throw "Could not resolve tenant ID. Pass -TenantId explicitly."
}

$brokerApp = Ensure-App -DisplayName $BrokerAppName
$downstreamApp = Ensure-App -DisplayName $DownstreamApiAppName

Ensure-ServicePrincipal -AppId $brokerApp.appId
Ensure-ServicePrincipal -AppId $downstreamApp.appId

if ([string]::IsNullOrWhiteSpace($DownstreamIdentifierUri)) {
    $DownstreamIdentifierUri = "api://$($downstreamApp.appId)"
}

$scopeId = Configure-DownstreamApiScope -App $downstreamApp -IdentifierUri $DownstreamIdentifierUri -ScopeName $DownstreamScopeName
Grant-DelegatedPermission -BrokerAppId $brokerApp.appId -DownstreamAppId $downstreamApp.appId -ScopeId $scopeId

$clientSecret = Create-OrRotateBrokerSecret -BrokerAppId $brokerApp.appId -Years $SecretYears
$tokenEndpoint = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$scopeValue = "$DownstreamIdentifierUri/.default"

$envBlock = @"
# Generated by scripts/bootstrap-entra-obo.ps1
SERVICENOW_OBO_TENANT_ID=$TenantId
SERVICENOW_OBO_CLIENT_ID=$($brokerApp.appId)
SERVICENOW_OBO_CLIENT_SECRET=$clientSecret
SERVICENOW_OBO_SCOPE=$scopeValue
SERVICENOW_OBO_TOKEN_ENDPOINT=$tokenEndpoint
# Runtime value from your upstream caller per request/session:
SERVICENOW_OBO_USER_ASSERTION=__SET_AT_RUNTIME__
"@

$envPath = Resolve-Path -Path .
$envOutFile = Join-Path -Path $envPath -ChildPath $OutputEnvFile
Set-Content -Path $envOutFile -Value $envBlock -Encoding UTF8

Write-Host ""
Write-Host "Entra OBO bootstrap complete."
Write-Host "Generated env settings file: $envOutFile"
Write-Host ""
Write-Host $envBlock
