import requests_mock

from virustotal.action_virustotal_scanip import VirusTotalScanIPAction

ip_results: dict = {
    "as_owner": "Unified Layer",
    "asn": 46606,
    "continent": "NA",
    "country": "US",
    "detected_downloaded_samples": [],
    "detected_urls": [
        {
            "positives": 2,
            "scan_date": "2019-06-21 04:26:40",
            "total": 70,
            "url": "http://apple-support-information.com/",
        },
        {
            "positives": 3,
            "scan_date": "2019-04-25 10:50:03",
            "total": 66,
            "url": "https://apple-support-information.com/",
        },
        {
            "positives": 6,
            "scan_date": "2017-10-21 14:14:08",
            "total": 64,
            "url": "http://www.apple-support-information.com/",
        },
        {
            "positives": 5,
            "scan_date": "2017-10-06 14:14:32",
            "total": 64,
            "url": "http://cdn-dmsaobject-activity.ml/",
        },
        {
            "positives": 4,
            "scan_date": "2017-09-17 00:06:16",
            "total": 64,
            "url": "http://cdn-dmsaobject-activity.ml/appleid.signin.com/",
        },
        {
            "positives": 4,
            "scan_date": "2017-09-05 08:48:24",
            "total": 65,
            "url": "https://cdn-dmsaobject-activity.ml/appleid.signin.com",
        },
        {
            "positives": 5,
            "scan_date": "2017-09-03 02:54:11",
            "total": 65,
            "url": "https://cdn-dmsaobject-activity.ml/appleid.signin.com/",
        },
        {
            "positives": 6,
            "scan_date": "2017-09-02 07:39:27",
            "total": 65,
            "url": "http://apple-login-security-usa.ga/",
        },
        {
            "positives": 4,
            "scan_date": "2017-09-01 19:03:13",
            "total": 65,
            "url": "https://appleid.apple.com.unauthorized-fraudstatement.com/",
        },
        {
            "positives": 9,
            "scan_date": "2017-08-31 23:13:24",
            "total": 65,
            "url": "http://validate-account.com/login.php",
        },
        {
            "positives": 2,
            "scan_date": "2017-08-30 10:15:38",
            "total": 65,
            "url": "http://webhelp-accservices.com/Login.php?sslchannel=true"
            "&sessionid=Z6oAjjtiv1q3Id3Sp9Nate2rtISEnAzgLjWTHPJyrNXA"
            "ciAoyx6W76QYIJUfCOWV2cVmjubknZR2JuC4",
        },
        {
            "positives": 2,
            "scan_date": "2017-08-30 06:18:23",
            "total": 65,
            "url": "http://legal-idapple.tk/",
        },
        {
            "positives": 9,
            "scan_date": "2017-08-28 14:57:41",
            "total": 65,
            "url": "http://resolutioncentre.net/",
        },
        {
            "positives": 7,
            "scan_date": "2017-08-27 05:05:25",
            "total": 65,
            "url": "http://paypall-worldwides.resolutioncentre.net/",
        },
        {
            "positives": 2,
            "scan_date": "2017-08-26 10:19:05",
            "total": 65,
            "url": "http://webhelp-accservices.com/Login.php?sslchannel=true"
            "&sessionid=2vwov8H2fdbR6RlaTJEiybC5WgqSUYUz0NR4YyfS"
            "3OqmWzaFjWUJ5V0VVnrD8RxzpNd3uT1E1HYVTj0r",
        },
        {
            "positives": 5,
            "scan_date": "2017-08-25 05:05:22",
            "total": 65,
            "url": "http://paypall-worldwides.local-area-centre.com/",
        },
        {
            "positives": 1,
            "scan_date": "2017-08-22 01:45:21",
            "total": 65,
            "url": "https://idmsa.signin.authenticate-login.ml/",
        },
        {
            "positives": 6,
            "scan_date": "2017-08-20 13:02:19",
            "total": 65,
            "url": "http://idmsa.authenticate-customer.ml/",
        },
    ],
    "network": "50.116.64.0/18",
    "resolutions": [
        {"hostname": "6dhelmets.com", "last_resolved": "2019-07-24 13:10:01"},
        {
            "hostname": "apple-login-security-usa.ga",
            "last_resolved": "2017-09-02 00:00:00",
        },
        {
            "hostname": "apple-support-information.com",
            "last_resolved": "2019-06-21 04:26:41",
        },
        {
            "hostname": "appleid.apple.com.unauthorized-fraudstatement.com",
            "last_resolved": "2017-09-01 00:00:00",
        },
        {"hostname": "bebecrew.com", "last_resolved": "2017-09-20 00:00:00"},
        {"hostname": "canada.6dhelmets.com", "last_resolved": "2019-04-18 05:02:40"},
        {
            "hostname": "cdn-dmsaobject-activity.ml",
            "last_resolved": "2017-09-03 00:00:00",
        },
        {"hostname": "europe.6dhelmets.com", "last_resolved": "2019-05-19 20:03:05"},
        {
            "hostname": "europedealers.6dhelmets.com",
            "last_resolved": "2019-05-19 20:03:05",
        },
        {
            "hostname": "idmsa.authenticate-customer.ml",
            "last_resolved": "2017-08-20 00:00:00",
        },
        {
            "hostname": "idmsa.signin.authenticate-login.ml",
            "last_resolved": "2017-08-22 00:00:00",
        },
        {"hostname": "legal-idapple.tk", "last_resolved": "2017-08-30 00:00:00"},
        {"hostname": "ns1.ngentod-kuda.com", "last_resolved": "2018-07-05 01:07:16"},
        {"hostname": "ns2.ngentod-kuda.com", "last_resolved": "2018-07-26 08:35:29"},
        {
            "hostname": "paypall-worldwides.local-area-centre.com",
            "last_resolved": "2017-08-25 00:00:00",
        },
        {
            "hostname": "paypall-worldwides.resolutioncentre.net",
            "last_resolved": "2017-08-27 00:00:00",
        },
        {
            "hostname": "problemsservice.services",
            "last_resolved": "2017-08-23 00:00:00",
        },
        {"hostname": "rebuilds.6dhelmets.com", "last_resolved": "2019-05-19 20:03:05"},
        {"hostname": "resolutioncentre.net", "last_resolved": "2017-08-26 00:00:00"},
        {"hostname": "server.6dhelmets.com", "last_resolved": "2019-01-29 04:20:11"},
        {
            "hostname": "sponsorship.6dhelmets.com",
            "last_resolved": "2019-05-19 20:03:05",
        },
        {"hostname": "staging.6dhelmets.com", "last_resolved": "2019-04-17 06:57:02"},
        {"hostname": "validate-account.com", "last_resolved": "2017-09-03 11:49:15"},
        {"hostname": "webhelp-accservices.com", "last_resolved": "2017-08-23 10:26:14"},
        {"hostname": "www.6dhelmets.com", "last_resolved": "2019-06-15 18:08:33"},
        {
            "hostname": "www.apple-support-information.com",
            "last_resolved": "2017-09-06 11:11:05",
        },
        {
            "hostname": "www.canada.6dhelmets.com",
            "last_resolved": "2019-04-18 05:02:39",
        },
        {
            "hostname": "www.europe.6dhelmets.com",
            "last_resolved": "2019-05-19 20:03:05",
        },
        {
            "hostname": "www.europedealers.6dhelmets.com",
            "last_resolved": "2019-05-19 20:03:05",
        },
        {
            "hostname": "www.rebuilds.6dhelmets.com",
            "last_resolved": "2019-05-19 20:03:05",
        },
        {
            "hostname": "www.sponsorship.6dhelmets.com",
            "last_resolved": "2019-05-19 20:03:05",
        },
        {
            "hostname": "www.staging.6dhelmets.com",
            "last_resolved": "2019-04-17 06:57:02",
        },
        {
            "hostname": "www.webhelp-accservices.com",
            "last_resolved": "2017-08-23 10:26:18",
        },
    ],
    "response_code": 1,
    "undetected_downloaded_samples": [
        {
            "date": "2019-06-18 14:09:46",
            "positives": 0,
            "sha256": "9278d16ed2fdcd5dc651615b0b8adc6b5" "5fb667a9d106a9891b861d4561d9a24",
            "total": 70,
        },
        {
            "date": "2017-09-03 02:59:12",
            "positives": 0,
            "sha256": "2afb8f01c8e1a2ff009f70f9b782960f9" "bc2303b37b36cadd1cdf61e224966b6",
            "total": 55,
        },
        {
            "date": "2017-08-30 10:15:42",
            "positives": 0,
            "sha256": "dad77b4e03da0b316a68760e47d7fa73d3" "8b6aee78c004fbf5cb41b5a5d83ebf",
            "total": 58,
        },
    ],
    "undetected_urls": [],
    "verbose_msg": "IP address in dataset",
    "whois": "Domain Name: datanation.biz\n"
    "Registry Domain ID: D49910571-BIZ\n"
    "Registrar WHOIS Server: whois.godaddy.com\n"
    "Registrar URL: whois.godaddy.com\n"
    "Updated Date: 2019-05-16T12:05:33Z\n"
    "Creation Date: 2012-05-11T02:27:44Z\n"
    "Registry Expiry Date: 2020-05-10T23:59:59Z\n"
    "Registrar: GoDaddy.com, Inc.\n"
    "Registrar IANA ID: 146\n"
    "Registrar Abuse Contact Email: abuse@godaddy.com\n"
    "Registrar Abuse Contact Phone: +1.4806242505\n"
    "Domain Status: clientTransferProhibited "
    "https://icann.org/epp#clientTransferProhibited\n"
    "Domain Status: clientDeleteProhibited "
    "https://icann.org/epp#clientDeleteProhibited\n"
    "Domain Status: clientRenewProhibited "
    "https://icann.org/epp#clientRenewProhibited\n"
    "Domain Status: clientUpdateProhibited "
    "https://icann.org/epp#clientUpdateProhibited\n"
    "Registrant Country: US\n"
    "Name Server: ns1.datanation.biz\n"
    "Name Server: ns2.datanation.biz\n"
    "DNSSEC: unsigned\n"
    "Domain Name: DATANATION.BIZ\n"
    "Registrar URL: http://www.godaddy.com\n"
    "Updated Date: 2019-05-11T12:05:33Z\n"
    "Registrar Registration Expiration Date: 2020-05-10T23:59:59Z\n"
    "Registrar: GoDaddy.com, LLC\n"
    "Domain Status: clientTransferProhibited "
    "http://www.icann.org/epp#clientTransferProhibited\n"
    "Domain Status: clientUpdateProhibited "
    "http://www.icann.org/epp#clientUpdateProhibited\n"
    "Domain Status: clientRenewProhibited "
    "http://www.icann.org/epp#clientRenewProhibited\n"
    "Domain Status: clientDeleteProhibited "
    "http://www.icann.org/epp#clientDeleteProhibited\n"
    "Name Server: NS1.DATANATION.BIZ\n"
    "Name Server: NS2.DATANATION.BIZ",
    "whois_timestamp": 1561814151,
}


def test_virustotal_scan_ip():
    vt: VirusTotalScanIPAction = VirusTotalScanIPAction()
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://www.virustotal.com/vtapi/v2/ip-address/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&ip=50.116.99.126",
            json=ip_results,
        )

        results: dict = vt.run({"ip": "50.116.99.126"})

        assert results == ip_results
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert (
            history[0].url == "https://www.virustotal.com/vtapi/v2/ip-address/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&ip=50.116.99.126"
        )
