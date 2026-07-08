[CmdletBinding()]
param(
    [string]$TenantId,
    [string]$BrokerAppName = "servicenow-mcp-obo-broker",
    [string]$InteractiveClientAppName = "servicenow-mcp-obo-interactive-client",
    [string]$BrokerScopeName = "user_impersonation",
    [string]$BrokerIdentifierUri,
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

function Configure-ApiScope {
    param(
        [Parameter(Mandatory = $true)]$App,
        [Parameter(Mandatory = $true)][string]$IdentifierUri,
        [Parameter(Mandatory = $true)][string]$ScopeName
    )

    $appDetailRaw = az rest --method GET --uri "https://graph.microsoft.com/v1.0/applications/$($App.id)" --output json
    $appDetail = $appDetailRaw | ConvertFrom-Json
    $existingScopes = @()
    if ($null -ne $appDetail.api -and $null -ne $appDetail.api.oauth2PermissionScopes) {
        $existingScopes = @($appDetail.api.oauth2PermissionScopes)
    }

    $matchingScope = $existingScopes | Where-Object { $_.value -eq $ScopeName } | Select-Object -First 1
    $identifierUris = @()
    if ($null -ne $appDetail.identifierUris) {
        $identifierUris = @($appDetail.identifierUris)
    }

    if ($matchingScope -and ($identifierUris -contains $IdentifierUri)) {
        Write-Host "Scope '$ScopeName' already configured on $IdentifierUri"
        return $matchingScope.id
    }

    $scopeId = if ($matchingScope) { $matchingScope.id } else { [Guid]::NewGuid().ToString() }
    $scopesForPatch = @()
    if ($matchingScope) {
        $scopesForPatch = $existingScopes
    } else {
        $scopesForPatch = @($existingScopes)
        $scopesForPatch += @{
            id = $scopeId
            value = $ScopeName
            type = "User"
            isEnabled = $true
            adminConsentDisplayName = "Access $ScopeName"
            adminConsentDescription = "Allow the app to access this API on behalf of the signed-in user."
            userConsentDisplayName = "Access $ScopeName"
            userConsentDescription = "Allow the app to access this API on your behalf."
        }
    }

    $patchBody = @{
        identifierUris = @($IdentifierUri)
        api = @{
            requestedAccessTokenVersion = 2
            oauth2PermissionScopes = @($scopesForPatch)
        }
    } | ConvertTo-Json -Depth 10 -Compress

    $tempBodyPath = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath ("servicenow-mcp-graph-patch-" + [Guid]::NewGuid().ToString() + ".json")
    Set-Content -Path $tempBodyPath -Value $patchBody -Encoding UTF8

    try {
        Write-Host "Configuring API scope '$ScopeName' on $IdentifierUri"
        az rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$($App.id)" --headers "Content-Type=application/json" --body "@$tempBodyPath" --output none
    } finally {
        Remove-Item -Path $tempBodyPath -Force -ErrorAction SilentlyContinue
    }

    return $scopeId
}

function Grant-DelegatedPermission {
    param(
        [Parameter(Mandatory = $true)][string]$ClientAppId,
        [Parameter(Mandatory = $true)][string]$ResourceAppId,
        [Parameter(Mandatory = $true)][string]$ScopeId,
        [Parameter(Mandatory = $true)][string]$ScopeName,
        [Parameter(Mandatory = $true)][string]$ClientLabel
    )

    Write-Host "Granting delegated permission to $ClientLabel"
    az ad app permission add --id $ClientAppId --api $ResourceAppId --api-permissions "$ScopeId=Scope" --output none
    az ad app permission grant --id $ClientAppId --api $ResourceAppId --scope $ScopeName --output none

    try {
        az ad app permission admin-consent --id $ClientAppId --output none
        Write-Host "Admin consent granted for $ClientLabel."
    } catch {
        Write-Warning "Admin consent could not be granted automatically. A tenant admin may need to run: az ad app permission admin-consent --id $ClientAppId"
    }
}

function Set-AppAsPublicClient {
    param([Parameter(Mandatory = $true)][string]$AppId)

    Write-Host "Enabling public client fallback for appId: $AppId"
    az ad app update --id $AppId --is-fallback-public-client true --public-client-redirect-uris "http://localhost" --output none
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
$interactiveClientApp = Ensure-App -DisplayName $InteractiveClientAppName
$downstreamApp = Ensure-App -DisplayName $DownstreamApiAppName

Ensure-ServicePrincipal -AppId $brokerApp.appId
Ensure-ServicePrincipal -AppId $interactiveClientApp.appId
Ensure-ServicePrincipal -AppId $downstreamApp.appId

Set-AppAsPublicClient -AppId $interactiveClientApp.appId

if ([string]::IsNullOrWhiteSpace($BrokerIdentifierUri)) {
    $BrokerIdentifierUri = "api://$($brokerApp.appId)"
}

if ([string]::IsNullOrWhiteSpace($DownstreamIdentifierUri)) {
    $DownstreamIdentifierUri = "api://$($downstreamApp.appId)"
}

$brokerScopeId = Configure-ApiScope -App $brokerApp -IdentifierUri $BrokerIdentifierUri -ScopeName $BrokerScopeName
$downstreamScopeId = Configure-ApiScope -App $downstreamApp -IdentifierUri $DownstreamIdentifierUri -ScopeName $DownstreamScopeName

Grant-DelegatedPermission -ClientAppId $brokerApp.appId -ResourceAppId $downstreamApp.appId -ScopeId $downstreamScopeId -ScopeName $DownstreamScopeName -ClientLabel "broker app"
Grant-DelegatedPermission -ClientAppId $interactiveClientApp.appId -ResourceAppId $brokerApp.appId -ScopeId $brokerScopeId -ScopeName $BrokerScopeName -ClientLabel "interactive client app"

$clientSecret = Create-OrRotateBrokerSecret -BrokerAppId $brokerApp.appId -Years $SecretYears
$tokenEndpoint = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$scopeValue = "$DownstreamIdentifierUri/.default"
$userScopeValue = "$BrokerIdentifierUri/$BrokerScopeName"

$envBlock = @"
# Generated by scripts/bootstrap-entra-obo.ps1
SERVICENOW_OBO_TENANT_ID=$TenantId
SERVICENOW_OBO_CLIENT_ID=$($brokerApp.appId)
SERVICENOW_OBO_CLIENT_SECRET=$clientSecret
SERVICENOW_OBO_SCOPE=$scopeValue
SERVICENOW_OBO_PUBLIC_CLIENT_ID=$($interactiveClientApp.appId)
SERVICENOW_OBO_USER_SCOPE=$userScopeValue
SERVICENOW_OBO_TOKEN_ENDPOINT=$tokenEndpoint
SERVICENOW_SN_JWT_TENANT_ID=$TenantId
SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID=$($brokerApp.appId)
# Set after ServiceNow registry provisioning:
# SERVICENOW_SN_JWT_CLIENT_ID=__SET_FROM_SERVICENOW__
# SERVICENOW_SN_JWT_PRIVATE_KEY_PATH=.servicenow-jwt/servicenow-jwt-private.pem
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
