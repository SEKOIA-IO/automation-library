from sekoia_automation.module import Module

from riskiq_module import (
    GetCurrentWhoisForDomain,
    GetWhoisRecordsAssociatedWithAddress,
    HostsByCertificateAction,
    PdnsHexAction,
    PdnsIPAction,
    PdnsNameAction,
    SslCertificateBySha1Action,
    SslCertificatesByHostNameAction,
    SslCertificatesByNameAction,
    SslCertificatesBySerialNumberAction,
    WhoisRecordsAssociatedWithEmailAddress,
    WhoisRecordsAssociatedWithName,
    WhoisRecordsAssociatedWithNameServer,
    WhoisRecordsAssociatedWithOrganization,
    WhoisRecordsAssociatedWithPhoneNumber,
)

if __name__ == "__main__":
    module = Module()
    module.register(PdnsIPAction, "pdns_ip")
    module.register(PdnsNameAction, "pdns_name")
    module.register(PdnsHexAction, "pdns_hex")
    module.register(SslCertificatesByHostNameAction, "ssl_cert_host")
    module.register(SslCertificatesBySerialNumberAction, "ssl_cert_serial_number")
    module.register(SslCertificateBySha1Action, "ssl_cert_sha1")
    module.register(HostsByCertificateAction, "ssl_host_cert")
    module.register(SslCertificatesByNameAction, "ssl_cert_name")
    module.register(GetWhoisRecordsAssociatedWithAddress, "whois_address")
    module.register(GetCurrentWhoisForDomain, "current_whois_domain")
    module.register(WhoisRecordsAssociatedWithEmailAddress, "whois_email")
    module.register(WhoisRecordsAssociatedWithName, "whois_name")
    module.register(WhoisRecordsAssociatedWithNameServer, "whois_nameserver")
    module.register(WhoisRecordsAssociatedWithOrganization, "whois_org")
    module.register(WhoisRecordsAssociatedWithPhoneNumber, "whois_phone")
    module.run()
