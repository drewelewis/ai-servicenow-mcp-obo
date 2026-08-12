[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertFrom-AzdEnvironmentValue {
    param([Parameter(Mandatory = $true)][string]$Value)

    $trimmedValue = $Value.Trim()
    if ($trimmedValue.StartsWith('"') -and $trimmedValue.EndsWith('"')) {
        try {
            return ConvertFrom-Json -InputObject $trimmedValue
        } catch {
            throw "Could not decode a quoted value from the active azd environment."
        }
    }
    return $trimmedValue
}

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
            $values[$matches[1]] = ConvertFrom-AzdEnvironmentValue -Value $matches[2]
        }
    }

    return $values
}

function ConvertTo-NormalizedScopes {
    param($Scopes)

    return @(
        @($Scopes) |
            ForEach-Object { @([string]$_ -split '\s+') } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Sort-Object -Unique
    )
}

function Compare-Scopes {
    param($Actual, $Expected)

    $actualScopes = @(ConvertTo-NormalizedScopes -Scopes $Actual)
    $expectedScopes = @(ConvertTo-NormalizedScopes -Scopes $Expected)
    return ($actualScopes.Count -eq $expectedScopes.Count) -and
        -not (Compare-Object -ReferenceObject $actualScopes -DifferenceObject $expectedScopes)
}

function Get-ConnectorOAuthFingerprint {
    param(
        [Parameter(Mandatory = $true)][string]$ClientId,
        [Parameter(Mandatory = $true)][string]$ClientSecret,
        [Parameter(Mandatory = $true)][string[]]$Scopes
    )

    $normalizedScopes = @(ConvertTo-NormalizedScopes -Scopes $Scopes) -join " "
    $fingerprintInput = "$ClientId`n$normalizedScopes`n$ClientSecret"
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($fingerprintInput))
        return ([System.BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha256.Dispose()
        $fingerprintInput = $null
    }
}

function Sync-PowerPlatformConnectorScopes {
    param(
        [Parameter(Mandatory = $true)][string]$PacPath,
        [Parameter(Mandatory = $true)][string]$ConnectorId,
        [Parameter(Mandatory = $true)][string]$ConnectorName,
        [Parameter(Mandatory = $true)][string[]]$ExpectedScopes,
        [Parameter(Mandatory = $true)][string]$ClientId,
        [Parameter(Mandatory = $true)][string]$ClientSecret,
        [string]$CurrentFingerprint
    )

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("servicenow-mcp-connector-" + [Guid]::NewGuid().ToString())
    $updatedRoot = "$tempRoot-verify"
    try {
        & $PacPath connector download --connector-id $ConnectorId --outputDirectory $tempRoot | Out-Null
        $propertiesPath = Join-Path $tempRoot "apiProperties.json"
        $definitionPath = Join-Path $tempRoot "apiDefinition.json"
        if (-not (Test-Path -Path $propertiesPath -PathType Leaf)) {
            throw "PAC did not download OAuth properties for Copilot Studio connector '$ConnectorName'."
        }
        if (-not (Test-Path -Path $definitionPath -PathType Leaf)) {
            throw "PAC did not download the API definition for Copilot Studio connector '$ConnectorName'."
        }

        $apiProperties = Get-Content -Path $propertiesPath -Raw | ConvertFrom-Json
        $oauthSettings = $apiProperties.properties.connectionParameters.token.oAuthSettings
        if ($null -eq $oauthSettings) {
            throw "Copilot Studio connector '$ConnectorName' does not expose OAuth settings."
        }
        if ($oauthSettings.PSObject.Properties["clientSecret"]) {
            throw "Downloaded connector '$ConnectorName' unexpectedly contains a client secret."
        }
        $expectedFingerprint = Get-ConnectorOAuthFingerprint `
            -ClientId $ClientId `
            -ClientSecret $ClientSecret `
            -Scopes $ExpectedScopes
        $scopesMatch = Compare-Scopes -Actual $oauthSettings.scopes -Expected $ExpectedScopes
        if ($scopesMatch -and $oauthSettings.clientId -eq $ClientId -and $CurrentFingerprint -eq $expectedFingerprint) {
            Write-Host "Copilot Studio connector '$ConnectorName' already has the expected OAuth configuration."
            return
        }

        $oauthSettings.scopes = @($ExpectedScopes)
        $oauthSettings.clientId = $ClientId
        $oauthSettings | Add-Member -NotePropertyName clientSecret -NotePropertyValue $ClientSecret -Force
        Set-Content -Path $propertiesPath -Value ($apiProperties | ConvertTo-Json -Depth 100) -Encoding UTF8
        & $PacPath connector update `
            --connector-id $ConnectorId `
            --api-definition-file $definitionPath `
            --api-properties-file $propertiesPath | Out-Null

        & $PacPath connector download --connector-id $ConnectorId --outputDirectory $updatedRoot | Out-Null
        $updatedPropertiesPath = Join-Path $updatedRoot "apiProperties.json"
        if (-not (Test-Path -Path $updatedPropertiesPath -PathType Leaf)) {
            throw "PAC did not return updated OAuth properties for Copilot Studio connector '$ConnectorName'."
        }
        $updatedProperties = Get-Content -Path $updatedPropertiesPath -Raw | ConvertFrom-Json
        $updatedScopes = $updatedProperties.properties.connectionParameters.token.oAuthSettings.scopes
        if (-not (Compare-Scopes -Actual $updatedScopes -Expected $ExpectedScopes)) {
            throw "OAuth scope reconciliation did not persist for Copilot Studio connector '$ConnectorName'."
        }
        $updatedClientId = $updatedProperties.properties.connectionParameters.token.oAuthSettings.clientId
        if ($updatedClientId -ne $ClientId) {
            throw "OAuth client ID reconciliation did not persist for Copilot Studio connector '$ConnectorName'."
        }
        azd env set COPILOT_STUDIO_CONNECTOR_OAUTH_FINGERPRINT $expectedFingerprint | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Could not store the OAuth configuration fingerprint for Copilot Studio connector '$ConnectorName'."
        }
        Write-Host "Updated Copilot Studio connector '$ConnectorName' with the expected OAuth configuration."
    } finally {
        Remove-Item -Path $tempRoot, $updatedRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Get-PowerPlatformRedirectUris {
    param(
        [Parameter(Mandatory = $true)][hashtable]$AzdValues,
        [Parameter(Mandatory = $true)][string]$TenantId
    )

    $profileName = $AzdValues["POWER_PLATFORM_PAC_PROFILE"]
    if ([string]::IsNullOrWhiteSpace($profileName)) {
        return @()
    }

    $pacPath = $AzdValues["POWER_PLATFORM_PAC_PATH"]
    if ([string]::IsNullOrWhiteSpace($pacPath)) {
        $pacCommand = Get-Command pac -ErrorAction SilentlyContinue
        if ($null -ne $pacCommand) {
            $pacPath = $pacCommand.Source
        } else {
            $pacLauncherPath = Join-Path $env:LOCALAPPDATA "Microsoft\PowerAppsCLI\pac.launcher.exe"
            if (Test-Path -Path $pacLauncherPath -PathType Leaf) {
                $pacPath = $pacLauncherPath
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($pacPath) -or -not (Test-Path -Path $pacPath -PathType Leaf)) {
        throw "Power Platform CLI was not found. Install PAC or set POWER_PLATFORM_PAC_PATH."
    }

    & $pacPath auth select --name $profileName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PAC authentication profile '$profileName' was not found. Create it before running azd up."
    }

    $organizationJson = ((& $pacPath org who --json) -join "`n")
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($organizationJson)) {
        throw "PAC profile '$profileName' is not authenticated or has no selected environment."
    }
    $organization = $organizationJson | ConvertFrom-Json

    $environmentId = $AzdValues["POWER_PLATFORM_ENVIRONMENT_ID"]
    if ([string]::IsNullOrWhiteSpace($environmentId)) {
        $environmentId = $organization.EnvironmentId
    }
    if ([string]::IsNullOrWhiteSpace($environmentId)) {
        throw "POWER_PLATFORM_ENVIRONMENT_ID is not set and PAC did not return an environment ID."
    }

    $connectorNamesJson = $AzdValues["COPILOT_STUDIO_CONNECTOR_DISPLAY_NAMES_JSON"]
    if ([string]::IsNullOrWhiteSpace($connectorNamesJson)) {
        $connectorNamesJson = '["ServiceNow MCP"]'
    }
    try {
        $parsedConnectorNames = ConvertFrom-Json -InputObject $connectorNamesJson
        $connectorNames = @($parsedConnectorNames | ForEach-Object { $_ })
    } catch {
        throw "COPILOT_STUDIO_CONNECTOR_DISPLAY_NAMES_JSON must be a JSON array of connector display names."
    }
    if ($connectorNames.Count -eq 0) {
        throw "COPILOT_STUDIO_CONNECTOR_DISPLAY_NAMES_JSON must contain at least one display name."
    }

    $brokerClientId = $AzdValues["SERVICENOW_OBO_CLIENT_ID"]
    if ([string]::IsNullOrWhiteSpace($brokerClientId)) {
        throw "SERVICENOW_OBO_CLIENT_ID is required to reconcile Copilot Studio OAuth scopes."
    }
    $copilotClientId = $AzdValues["COPILOT_STUDIO_CLIENT_ID"]
    if ([string]::IsNullOrWhiteSpace($copilotClientId)) {
        throw "COPILOT_STUDIO_CLIENT_ID is required to reconcile Copilot Studio OAuth settings."
    }
    $copilotClientSecret = $AzdValues["COPILOT_STUDIO_CLIENT_SECRET"]
    if ([string]::IsNullOrWhiteSpace($copilotClientSecret)) {
        throw "COPILOT_STUDIO_CLIENT_SECRET is required to reconcile Copilot Studio OAuth settings."
    }
    $currentOAuthFingerprint = $AzdValues["COPILOT_STUDIO_CONNECTOR_OAUTH_FINGERPRINT"]
    $expectedScopes = @(
        "openid",
        "profile",
        "offline_access",
        "api://$brokerClientId/user_impersonation"
    )

    $connectorListJson = ((& $pacPath connector list --json) -join "`n")
    if ([string]::IsNullOrWhiteSpace($connectorListJson)) {
        throw "PAC did not return connectors for OAuth scope reconciliation."
    }
    $pacConnectors = @((ConvertFrom-Json -InputObject $connectorListJson) | ForEach-Object { $_ })

    $accessToken = az account get-access-token --tenant $TenantId --resource "https://service.powerapps.com/" --query accessToken --output tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($accessToken)) {
        throw "Azure CLI could not acquire a Power Apps access token for callback discovery."
    }

    try {
        $escapedEnvironmentId = [uri]::EscapeDataString($environmentId)
        $apiUri = "https://api.powerapps.com/providers/Microsoft.PowerApps/scopes/admin/environments/$escapedEnvironmentId/apis?api-version=2016-11-01"
        $response = Invoke-RestMethod -Method Get -Uri $apiUri -Headers @{ Authorization = "Bearer $accessToken" }
    } finally {
        $accessToken = $null
    }

    $redirectUris = @()
    foreach ($connectorName in $connectorNames) {
        $connector = @($response.value) |
            Where-Object { $_.properties.displayName -eq $connectorName } |
            Sort-Object { $_.properties.changedTime } -Descending |
            Select-Object -First 1
        if ($null -eq $connector) {
            throw "Copilot Studio connector '$connectorName' was not found in Power Platform environment '$environmentId'."
        }

        $redirectUrl = $connector.properties.connectionParameters.token.oAuthSettings.redirectUrl
        if ([string]::IsNullOrWhiteSpace($redirectUrl)) {
            throw "Copilot Studio connector '$connectorName' does not expose an OAuth callback URL."
        }

        $matchingPacConnectors = @($pacConnectors | Where-Object { $_.DisplayName -eq $connectorName })
        if ($matchingPacConnectors.Count -ne 1) {
            throw "Expected exactly one PAC connector named '$connectorName', but found $($matchingPacConnectors.Count)."
        }
        Sync-PowerPlatformConnectorScopes `
            -PacPath $pacPath `
            -ConnectorId $matchingPacConnectors[0].ConnectorId `
            -ConnectorName $connectorName `
            -ExpectedScopes $expectedScopes `
            -ClientId $copilotClientId `
            -ClientSecret $copilotClientSecret `
            -CurrentFingerprint $currentOAuthFingerprint

        $redirectUris += $redirectUrl
        Write-Host "Discovered the OAuth callback for Copilot Studio connector '$connectorName'."
    }

    return @($redirectUris | Select-Object -Unique)
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

$copilotStudioRedirectUris = @(Get-PowerPlatformRedirectUris -AzdValues $azdValues -TenantId $tenantId)
if ($copilotStudioRedirectUris.Count -eq 0 -and $azdValues.ContainsKey("COPILOT_STUDIO_REDIRECT_URI")) {
    $copilotStudioRedirectUris = @($azdValues["COPILOT_STUDIO_REDIRECT_URI"])
}
if ($copilotStudioRedirectUris.Count -gt 0) {
    $bootstrapParameters["CopilotStudioRedirectUris"] = $copilotStudioRedirectUris
}

Write-Host "Provisioning Entra applications for the active azd environment."
& (Join-Path $PSScriptRoot "bootstrap-entra-obo.ps1") @bootstrapParameters