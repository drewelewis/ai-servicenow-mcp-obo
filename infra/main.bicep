targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the azd environment; used to derive resource names and tag resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources.')
param location string

// ---------------------------------------------------------------------------
// Application configuration (non-secret). Sourced from azd environment values.
// ---------------------------------------------------------------------------

@description('ServiceNow instance URL, e.g. https://dev123456.service-now.com/')
param serviceNowInstanceUrl string

@description('Entra tenant ID used to validate incoming user tokens.')
param snJwtTenantId string

@description('Expected incoming token audience / upstream client ID (the broker app).')
param snJwtUpstreamClientId string

@description('ServiceNow OAuth JWT-bearer client ID (the oauth_jwt record client_id).')
param snJwtClientId string

@description('ServiceNow OAuth token endpoint. Defaults to <instance>/oauth_token.do when empty.')
param snJwtTokenEndpoint string = ''

@description('Public JWKS URL that ServiceNow uses to verify the signed assertion.')
param snJwtJwksUrl string

@description('Claim used as the ServiceNow subject (default preferred_username).')
param snJwtUserClaimSource string = 'preferred_username'

// ---------------------------------------------------------------------------
// Secrets (stored in Key Vault). Provide via azd environment values.
// The private key is passed base64-encoded to avoid multiline handling issues.
// ---------------------------------------------------------------------------

@secure()
@description('Base64-encoded PEM private key used to sign the ServiceNow JWT assertion.')
param snJwtPrivateKeyBase64 string = ''

@secure()
@description('Optional ServiceNow OAuth client secret for the JWT-bearer client.')
param snJwtClientSecret string = ''

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    serviceNowInstanceUrl: serviceNowInstanceUrl
    snJwtTenantId: snJwtTenantId
    snJwtUpstreamClientId: snJwtUpstreamClientId
    snJwtClientId: snJwtClientId
    snJwtTokenEndpoint: snJwtTokenEndpoint
    snJwtJwksUrl: snJwtJwksUrl
    snJwtUserClaimSource: snJwtUserClaimSource
    snJwtPrivateKeyBase64: snJwtPrivateKeyBase64
    snJwtClientSecret: snJwtClientSecret
  }
}

output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.AZURE_CONTAINER_REGISTRY_NAME
output AZURE_KEY_VAULT_ENDPOINT string = resources.outputs.AZURE_KEY_VAULT_ENDPOINT
output AZURE_KEY_VAULT_NAME string = resources.outputs.AZURE_KEY_VAULT_NAME
output SERVICE_MCP_URI string = resources.outputs.SERVICE_MCP_URI
