### Configure

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
3. Type a description and select the desired expiration period
4. Click `Add`
5. Copy the `Value` of the client secret

#### Add permissions

1. Go to `Manage` > `API permissions`
2. Click `Add a permissions`
3. On the right panel, Select `Microsoft APIs` tab
4. Click `Microsoft Graph`
5. Click `Application permissions`
6. Select the following permissions
    - Mail.ReadWrite
    - Mail.Send
    - User.Read.All
7. Click `Add permissions`
8. In the `API permissions` page, click `Grant admin consent for TENANT_NAME`
9. Click `Yes` in the `Grant admin consent confirmation` modal