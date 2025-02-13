## Configuration

### Collect events

#### Create an Azure application

1. On the Azure Portal, in the search bar, go to `App registrations`
2. Click `+ New registration`
3. Type a name
4. Select `Accounts in this organizational directory only` option as account type
5. Click `Register`
6. From the `Overview` page, copy `Application (client) ID` and `Directory (tenant) ID`


#### Create a client secret

1. Go to `Manage` > `Certificates & secrets`
2. Click `+ New client secret`
3. Type a description and select the desirated expiration period
4. Click `Add`
5. Copy the `Value` of the client secret

#### Add permissions

1. Go to `Manage` > `API permissions`
2. Click `Add a permissions`
3. On the right panel, Select `APIs my organization uses` tab
4. Click `Office 365 Management APIs`
5. Click `Application permissions`
6. Select `ActivityFeed.Read`
7. Click `Add permissions`
8. In the `API permissions` page, click `Grant admin consent for TENANT_NAME`
9. Click `Yes` in the `Grant admin consent confirmation` modal

#### Install Agent

1. On security.microsoft.com, go to `System > Parameters`
2. Click `Endpoints` 
3. Go to `Device Management > Onboarding`
4. Download the Integration package

[Read More](https://learn.microsoft.com/en-us/defender-endpoint/configure-endpoints-script)

#### Create an application with the permission

1. In Microsoft EntraID, create a new application under `App registrations`.
2. For the permissions, go to `API permission`
3. Click `+ Add a permission`. Select `APIs my organization uses` and type `WindowsDefenderATP`. 
4. Select `WindowsDefenderATP`.
5. In the permissions, select:
   - Machine.Isolate
   - Machine.Offboard
   - Machine.Read.All
   - Machine.RestrictExecution
   - Machine.Scan
   - Machine.StopAndQuarantine
   - Ti.Read.All
   - Ti.ReadWrite
   - Ti.ReadWrite.All
   - Alert.ReadWrite.All
6. After permissions selection, grant the admin consent.
                          
[Read More](https://learn.microsoft.com/en-us/defender-endpoint/api/exposed-apis-create-app-webapp)