@description('Primary location for all resources.')
param location string

@description('Tags applied to all resources.')
param tags object

@description('Deterministic token used to build globally-unique resource names.')
@minLength(13)
@maxLength(13)
param resourceToken string

param serviceNowInstanceUrl string
param snJwtTenantId string
param snJwtUpstreamClientId string
param snJwtClientId string
param snJwtTokenEndpoint string
param snJwtJwksUrl string
param snJwtUserClaimSource string

@secure()
param snJwtPrivateKeyBase64 string

@secure()
param snJwtClientSecret string

// Service name must match the service key in azure.yaml so azd can target the app.
var serviceName = 'mcp'
var containerPort = 8000

var hasPrivateKey = !empty(snJwtPrivateKeyBase64)
var hasClientSecret = !empty(snJwtClientSecret)

// Built-in role definition IDs
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

// ---------------------------------------------------------------------------
// Identity
// ---------------------------------------------------------------------------

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${resourceToken}'
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------
// Networking (VNet-integrated Container Apps + private Key Vault)
// ---------------------------------------------------------------------------

var acaSubnetName = 'snet-aca'
var peSubnetName = 'snet-pep'

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: 'vnet-${resourceToken}'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/16'
      ]
    }
    subnets: [
      {
        // Infrastructure subnet for the Container Apps environment (Consumption).
        // Requires a /23 and delegation to Microsoft.App/environments.
        name: acaSubnetName
        properties: {
          addressPrefix: '10.0.0.0/23'
          delegations: [
            {
              name: 'aca'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        // Subnet dedicated to private endpoints.
        name: peSubnetName
        properties: {
          addressPrefix: '10.0.2.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource acaSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' existing = {
  parent: vnet
  name: acaSubnetName
}

resource peSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' existing = {
  parent: vnet
  name: peSubnetName
}

// ---------------------------------------------------------------------------
// Observability
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      searchVersion: 1
    }
  }
}

// ---------------------------------------------------------------------------
// Container Registry
// ---------------------------------------------------------------------------

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: 'acr${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, identity.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

// ---------------------------------------------------------------------------
// Key Vault (RBAC) + secrets
// ---------------------------------------------------------------------------

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Disabled'
  }
}

resource keyVaultSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identity.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
  }
}

resource privateKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (hasPrivateKey) {
  parent: keyVault
  name: 'sn-jwt-private-key'
  properties: {
    value: base64ToString(snJwtPrivateKeyBase64)
  }
}

resource clientSecretSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (hasClientSecret) {
  parent: keyVault
  name: 'sn-jwt-client-secret'
  properties: {
    value: snJwtClientSecret
  }
}

// Private endpoint + private DNS so the Container App reaches Key Vault privately.
resource keyVaultDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
  tags: tags
}

resource keyVaultDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: keyVaultDnsZone
  name: 'link-${resourceToken}'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource keyVaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: 'pe-kv-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'kv'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

resource keyVaultPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: keyVaultPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'vault'
        properties: {
          privateDnsZoneId: keyVaultDnsZone.id
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Container Apps environment + app
// ---------------------------------------------------------------------------

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: acaSubnet.id
      internal: false
    }
  }
}

// Base (non-secret) environment variables always present on the app.
var baseEnv = [
  {
    name: 'SERVICENOW_INSTANCE_URL'
    value: serviceNowInstanceUrl
  }
  {
    name: 'SERVICENOW_SN_JWT_TENANT_ID'
    value: snJwtTenantId
  }
  {
    name: 'SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID'
    value: snJwtUpstreamClientId
  }
  {
    name: 'SERVICENOW_SN_JWT_CLIENT_ID'
    value: snJwtClientId
  }
  {
    name: 'SERVICENOW_SN_JWT_TOKEN_ENDPOINT'
    value: snJwtTokenEndpoint
  }
  {
    name: 'SERVICENOW_SN_JWT_JWKS_URL'
    value: snJwtJwksUrl
  }
  {
    name: 'SERVICENOW_SN_JWT_USER_CLAIM_SOURCE'
    value: snJwtUserClaimSource
  }
  {
    name: 'FASTMCP_HOST'
    value: '0.0.0.0'
  }
  {
    name: 'FASTMCP_PORT'
    value: string(containerPort)
  }
]

// Secret-backed environment variables, added only when the secret was provided.
var privateKeyEnv = hasPrivateKey ? [
  {
    name: 'SERVICENOW_SN_JWT_PRIVATE_KEY'
    secretRef: 'sn-jwt-private-key'
  }
] : []

var clientSecretEnv = hasClientSecret ? [
  {
    name: 'SERVICENOW_SN_JWT_CLIENT_SECRET'
    secretRef: 'sn-jwt-client-secret'
  }
] : []

// Container App secret references pointing at Key Vault.
var privateKeySecretRef = hasPrivateKey ? [
  {
    name: 'sn-jwt-private-key'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/sn-jwt-private-key'
    identity: identity.id
  }
] : []

var clientSecretSecretRef = hasClientSecret ? [
  {
    name: 'sn-jwt-client-secret'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/sn-jwt-client-secret'
    identity: identity.id
  }
] : []

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${serviceName}-${resourceToken}'
  location: location
  tags: union(tags, { 'azd-service-name': serviceName })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: containerPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: concat(privateKeySecretRef, clientSecretSecretRef)
    }
    template: {
      containers: [
        {
          name: serviceName
          // Placeholder image; azd replaces this on `azd deploy`.
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: concat(baseEnv, privateKeyEnv, clientSecretEnv)
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
  dependsOn: [
    acrPullAssignment
    keyVaultSecretsUserAssignment
    privateKeySecret
    clientSecretSecret
    keyVaultPrivateDnsZoneGroup
  ]
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.name
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.properties.vaultUri
output AZURE_KEY_VAULT_NAME string = keyVault.name
output SERVICE_MCP_URI string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
