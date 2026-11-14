## How to configure Microsoft Windows Server module

The module runs PowerShell commands on the remote server through WinRM, authenticating with CredSSP. WinRM and CredSSP must therefore be enabled on the server.

### Prerequisites

Make sure you can access the remote server with Administrator privileges, and that it accepts remote connections on port `5985` (WinRM over HTTP, the port the module connects to). Port `5986` (WinRM over HTTPS) is only needed if you also set up an HTTPS listener (see the optional step below).

You can find more information about the WinRM configuration in the [Microsoft documentation](https://docs.microsoft.com/en-us/windows/win32/winrm/installation-and-configuration-for-windows-remote-management).

If you are using an Azure VM, please check this [documentation](https://docs.microsoft.com/en-us/azure/virtual-machines/windows/winrm) and allow the WinRM ports in the `Network settings` tab of your machine. Below is an example of security rules for WinRM.

![Azure VM WinRM](docs/assets/security-rules.png)

### Configure WinRM on the remote server

1. Open a PowerShell console as Administrator on the remote server
2. Execute the command `Enable-PSRemoting -force`

    ![Enable-PSRemoting](docs/assets/1-psremoting.png)

3. Execute the command `winrm quickconfig`

    ![Quick Config](docs/assets/2-winrm-quick-config.png)

4. Create the firewall rules allowing traffic to the remote server on port `5985` for WinRM HTTP and `5986` for WinRM HTTPS

    ```powershell
    netsh advfirewall firewall add rule name="WinRM-HTTP" dir=in localport=5985 protocol=TCP action=allow
    netsh advfirewall firewall add rule name="WinRM-HTTPS" dir=in localport=5986 protocol=TCP action=allow
    ```

    ![Netsh](docs/assets/3-netsh.png)

5. (Optional) Create a certificate for WinRM HTTPS and add an HTTPS listener with the certificate thumbprint

    ```powershell
    $cert = New-SelfSignedCertificate -DnsName "<DNS or IP>" -CertStoreLocation cert:\
    winrm create winrm/config/Listener?Address=*+Transport=HTTPS "@{Hostname=`"<DNS_Name or IP>`";CertificateThumbprint=`"$($cert.ThumbPrint)`"}"
    ```

    ![New-SelfSignedCertificate](docs/assets/4-new-self-signed-certificate.png)

6. Validate the listeners with `winrm e winrm/config/listener`

    ![Validate listeners](docs/assets/5-validate-listeners.png)

7. Enable CredSSP on the server with `Enable-WSManCredSSP -Role Server`

    ![WSManCredSSP](docs/assets/6-wsmancredssp.png)
