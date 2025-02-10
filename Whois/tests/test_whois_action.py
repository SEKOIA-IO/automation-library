from unittest.mock import patch

import pytest
from whois.parser import WhoisEntry

from whois_module.whois_action import WhoisAction, is_ip_adress, extract_domain_from_url


@pytest.fixture
def raw_google_whois():
    return """
   Domain Name: GOOGLE.COM
   Registry Domain ID: 2138514_DOMAIN_COM-VRSN
   Registrar WHOIS Server: whois.markmonitor.com
   Registrar URL: http://www.markmonitor.com
   Updated Date: 2019-09-09T15:39:04Z
   Creation Date: 1997-09-15T04:00:00Z
   Registry Expiry Date: 2028-09-14T04:00:00Z
   Registrar: MarkMonitor Inc.
   Registrar IANA ID: 292
   Registrar Abuse Contact Email: abusecomplaints@markmonitor.com
   Registrar Abuse Contact Phone: +1.2086851750
   Domain Status: clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited
   Domain Status: clientTransferProhibited https://icann.org/epp#clientTransferProhibited
   Domain Status: clientUpdateProhibited https://icann.org/epp#clientUpdateProhibited
   Domain Status: serverDeleteProhibited https://icann.org/epp#serverDeleteProhibited
   Domain Status: serverTransferProhibited https://icann.org/epp#serverTransferProhibited
   Domain Status: serverUpdateProhibited https://icann.org/epp#serverUpdateProhibited
   Name Server: NS1.GOOGLE.COM
   Name Server: NS2.GOOGLE.COM
   Name Server: NS3.GOOGLE.COM
   Name Server: NS4.GOOGLE.COM
   DNSSEC: unsigned
   URL of the ICANN Whois Inaccuracy Complaint Form: https://www.icann.org/wicf/
>>> Last update of whois database: 2025-02-10T09:25:48Z <<<

For more information on Whois status codes, please visit https://icann.org/epp

NOTICE: The expiration date displayed in this record is the date the
registrar's sponsorship of the domain name registration in the registry is
currently set to expire. This date does not necessarily reflect the expiration
date of the domain name registrant's agreement with the sponsoring
registrar.  Users may consult the sponsoring registrar's Whois database to
view the registrar's reported date of expiration for this registration.

TERMS OF USE: You are not authorized to access or query our Whois
database through the use of electronic processes that are high-volume and
automated except as reasonably necessary to register domain names or
modify existing registrations; the Data in VeriSign Global Registry
Services' ("VeriSign") Whois database is provided by VeriSign for
information purposes only, and to assist persons in obtaining information
about or related to a domain name registration record. VeriSign does not
guarantee its accuracy. By submitting a Whois query, you agree to abide
by the following terms of use: You agree that you may use this Data only
for lawful purposes and that under no circumstances will you use this Data
to: (1) allow, enable, or otherwise support the transmission of mass
unsolicited, commercial advertising or solicitations via e-mail, telephone,
or facsimile; or (2) enable high volume, automated, electronic processes
that apply to VeriSign (or its computer systems). The compilation,
repackaging, dissemination or other use of this Data is expressly
prohibited without the prior written consent of VeriSign. You agree not to
use electronic processes that are automated and high-volume to access or
query the Whois database except as reasonably necessary to register
domain names or modify existing registrations. VeriSign reserves the right
to restrict your access to the Whois database in its sole discretion to ensure
operational stability.  VeriSign may restrict or terminate your access to the
Whois database for failure to abide by these terms of use. VeriSign
reserves the right to modify these terms at any time.

The Registry database contains ONLY .COM, .NET, .EDU domains and
Registrars.
Domain Name: google.com
Registry Domain ID: 2138514_DOMAIN_COM-VRSN
Registrar WHOIS Server: whois.markmonitor.com
Registrar URL: http://www.markmonitor.com
Updated Date: 2024-08-02T02:17:33+0000
Creation Date: 1997-09-15T07:00:00+0000
Registrar Registration Expiration Date: 2028-09-13T07:00:00+0000
Registrar: MarkMonitor, Inc.
Registrar IANA ID: 292
Registrar Abuse Contact Email: abusecomplaints@markmonitor.com
Registrar Abuse Contact Phone: +1.2086851750
Domain Status: clientUpdateProhibited (https://www.icann.org/epp#clientUpdateProhibited)
Domain Status: clientTransferProhibited (https://www.icann.org/epp#clientTransferProhibited)
Domain Status: clientDeleteProhibited (https://www.icann.org/epp#clientDeleteProhibited)
Domain Status: serverUpdateProhibited (https://www.icann.org/epp#serverUpdateProhibited)
Domain Status: serverTransferProhibited (https://www.icann.org/epp#serverTransferProhibited)
Domain Status: serverDeleteProhibited (https://www.icann.org/epp#serverDeleteProhibited)
Registrant Organization: Google LLC
Registrant State/Province: CA
Registrant Country: US
Registrant Email: Select Request Email Form at https://domains.markmonitor.com/whois/google.com
Admin Organization: Google LLC
Admin State/Province: CA
Admin Country: US
Admin Email: Select Request Email Form at https://domains.markmonitor.com/whois/google.com
Tech Organization: Google LLC
Tech State/Province: CA
Tech Country: US
Tech Email: Select Request Email Form at https://domains.markmonitor.com/whois/google.com
Name Server: ns3.google.com
Name Server: ns4.google.com
Name Server: ns2.google.com
Name Server: ns1.google.com
DNSSEC: unsigned
URL of the ICANN WHOIS Data Problem Reporting System: http://wdprs.internic.net/
>>> Last update of WHOIS database: 2025-02-10T09:21:41+0000 <<<

For more information on WHOIS status codes, please visit:
  https://www.icann.org/resources/pages/epp-status-codes

If you wish to contact this domain’s Registrant, Administrative, or Technical
contact, and such email address is not visible above, you may do so via our web
form, pursuant to ICANN’s Temporary Specification. To verify that you are not a
robot, please enter your email address to receive a link to a page that
facilitates email communication with the relevant contact(s).

Web-based WHOIS:
  https://domains.markmonitor.com/whois

If you have a legitimate interest in viewing the non-public WHOIS details, send
your request and the reasons for your request to whoisrequest@markmonitor.com
and specify the domain name in the subject line. We will review that request and
may ask for supporting documentation and explanation.

The data in MarkMonitor’s WHOIS database is provided for information purposes,
and to assist persons in obtaining information about or related to a domain
name’s registration record. While MarkMonitor believes the data to be accurate,
the data is provided "as is" with no guarantee or warranties regarding its
accuracy.

By submitting a WHOIS query, you agree that you will use this data only for
lawful purposes and that, under no circumstances will you use this data to:
  (1) allow, enable, or otherwise support the transmission by email, telephone,
or facsimile of mass, unsolicited, commercial advertising, or spam; or
  (2) enable high volume, automated, or electronic processes that send queries,
data, or email to MarkMonitor (or its systems) or the domain name contacts (or
its systems).

MarkMonitor reserves the right to modify these terms at any time.

By submitting this query, you agree to abide by this policy.

MarkMonitor Domain Management(TM)
Protecting companies and consumers in a digital world.

Visit MarkMonitor at https://www.markmonitor.com
Contact us at +1.8007459229
In Europe, at +44.02032062220"""


@pytest.fixture
def whois_results(raw_google_whois):
    return WhoisEntry(
        "google.com",
        raw_google_whois,
    )


def test_is_ip_adress():
    assert is_ip_adress("8.8.8.8")
    assert not is_ip_adress("8.8.8")
    assert not is_ip_adress("google.com")
    assert is_ip_adress("2001:0000:130F:0000:0000:09C0:876A:130B")


def test_extract_domain_from_url():
    assert extract_domain_from_url("google.com") == "google.com"
    assert extract_domain_from_url("http://google.com") == "google.com"
    assert extract_domain_from_url("8.8.8.8") == "8.8.8.8"
    assert extract_domain_from_url("https://raw.githubusercontent.com/path") == "githubusercontent.com"
    assert extract_domain_from_url("raw.githubusercontent.com/path") == "githubusercontent.com"


def test_whois_action(whois_results, raw_google_whois):
    action = WhoisAction()

    with patch("whois.whois", return_value=whois_results):
        results = action.run({"query": "google.com"})

        assert results.get("Domain").get("Whois").get("CreationDate") == "1997-09-15 07:00:00"
        assert results.get("Domain").get("Whois").get("UpdatedDate") == "2024-08-02 02:17:33"
        assert results.get("Domain").get("Whois").get("ExpirationDate") == "2028-09-13 07:00:00"
        assert results == {
            "Domain": {
                "Name": "GOOGLE.COM",
                "Whois": {
                    "Domain": "GOOGLE.COM",
                    "DomainStatus": [
                        "clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited",
                        "clientTransferProhibited https://icann.org/epp#clientTransferProhibited",
                        "clientUpdateProhibited https://icann.org/epp#clientUpdateProhibited",
                        "serverDeleteProhibited https://icann.org/epp#serverDeleteProhibited",
                        "serverTransferProhibited https://icann.org/epp#serverTransferProhibited",
                        "serverUpdateProhibited https://icann.org/epp#serverUpdateProhibited",
                        "clientUpdateProhibited (https://www.icann.org/epp#clientUpdateProhibited)",
                        "clientTransferProhibited (https://www.icann.org/epp#clientTransferProhibited)",
                        "clientDeleteProhibited (https://www.icann.org/epp#clientDeleteProhibited)",
                        "serverUpdateProhibited (https://www.icann.org/epp#serverUpdateProhibited)",
                        "serverTransferProhibited (https://www.icann.org/epp#serverTransferProhibited)",
                        "serverDeleteProhibited (https://www.icann.org/epp#serverDeleteProhibited)",
                    ],
                    "DNSSec": "unsigned",
                    "Raw": raw_google_whois,
                    "NameServers": [
                        "NS1.GOOGLE.COM",
                        "NS2.GOOGLE.COM",
                        "NS3.GOOGLE.COM",
                        "NS4.GOOGLE.COM",
                        "ns3.google.com",
                        "ns4.google.com",
                        "ns2.google.com",
                        "ns1.google.com",
                    ],
                    "CreationDate": "1997-09-15 07:00:00",
                    "UpdatedDate": "2024-08-02 02:17:33",
                    "ExpirationDate": "2028-09-13 07:00:00",
                    "Registrar": {
                        "Name": "MarkMonitor, Inc.",
                        "AbuseEmail": "abusecomplaints@markmonitor.com",
                    },
                    "Registrant": {
                        "Name": "None",
                        "Email": "whoisrequest@markmonitor.com",
                    },
                },
            }
        }
