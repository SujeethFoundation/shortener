@description('Globally unique storage-account name.')
param storageAccountName string
@description('Globally unique Function App name.')
param functionAppName string
param location string = resourceGroup().location
@description('Public base URL used in API responses.')
param shortLinkBaseUrl string
@description('Comma-separated Entra object IDs allowed to administer links.')
param adminObjectIds string

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { allowBlobPublicAccess: false, minimumTlsVersion: 'TLS1_2' }
}
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${functionAppName}-plan'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
  properties: { reserved: true }
}
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${functionAppName}-insights'
  location: location
  kind: 'web'
  properties: { Application_Type: 'web' }
}
resource site 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: { linuxFxVersion: 'Python|3.11', minTlsVersion: '1.2', ftpsState: 'Disabled', appSettings: [
      { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
      { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storage.listKeys().keys[0].value}' }
      { name: 'SHORTLINKS_TABLE_NAME', value: 'ShortLinks' }
      { name: 'SHORTLINK_BASE_URL', value: shortLinkBaseUrl }
      { name: 'ADMIN_OBJECT_IDS', value: adminObjectIds }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
    ] }
  }
}
// Configure Entra Easy Auth in the portal or add your tenant/client IDs in a deployment-specific module.
// Keep unauthenticated requests allowed globally: public redirect routes must stay public.
output functionAppHostName string = site.properties.defaultHostName
output storageAccountId string = storage.id
