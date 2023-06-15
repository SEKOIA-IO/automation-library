import urllib.parse

import requests_mock

from virustotal.action_virustotal_scandomain import VirusTotalScanDomainAction

domain_results: dict = {
    "BitDefender category": "parked",
    "Dr.Web category": "known infection source",
    "Forcepoint ThreatSeeker category": "uncategorized",
    "Websense ThreatSeeker category": "uncategorized",
    "Webutation domain info": {
        "Adult content": "yes",
        "Safety score": 40,
        "Verdict": "malicious",
    },
    "categories": ["parked", "uncategorized"],
    "detected_downloaded_samples": [
        {
            "date": "2013-06-20 18:51:30",
            "positives": 2,
            "sha256": "cd8553d9b24574467f381d13c7e0e1eb1" "e58d677b9484bd05b9c690377813e54",
            "total": 46,
        }
    ],
    "detected_referrer_samples": [
        {
            "date": "2019-05-07 08:21:45",
            "positives": 1,
            "sha256": "10d3487aae5fed7f5e8a227e4eaef6" "1ef84e1d9857c02b50d40206ea81962699",
            "total": 72,
        }
    ],
    "detected_urls": [
        {
            "positives": 5,
            "scan_date": "2019-07-30 06:20:19",
            "total": 71,
            "url": "http://027.ru/adobe/flash_install_v10x1.php",
        },
        {
            "positives": 2,
            "scan_date": "2019-06-10 20:02:08",
            "total": 70,
            "url": "http://027.ru/",
        },
        {
            "positives": 2,
            "scan_date": "2019-03-14 11:13:22",
            "total": 66,
            "url": "http://027.ru/15.jpg",
        },
        {
            "positives": 3,
            "scan_date": "2018-12-17 04:54:05",
            "total": 70,
            "url": "https://027.ru/",
        },
        {
            "positives": 4,
            "scan_date": "2018-10-31 09:45:45",
            "total": 70,
            "url": "http://027.ru/track.php?domain=027.ru&caf=1&toggle=answercheck",
        },
        {
            "positives": 3,
            "scan_date": "2018-09-17 17:55:09",
            "total": 68,
            "url": "http://027.ru/track.php?domain=027.ru&amp;caf=1" "&amp;toggle=answercheck",
        },
        {
            "positives": 4,
            "scan_date": "2018-09-09 23:38:30",
            "total": 69,
            "url": "http://027.ru/track.php?domain=027",
        },
        {
            "positives": 2,
            "scan_date": "2018-04-15 16:01:20",
            "total": 67,
            "url": "http://027.ru/lol",
        },
        {
            "positives": 2,
            "scan_date": "2018-03-31 14:34:40",
            "total": 67,
            "url": "http://027.ru/lol?lldas=das",
        },
        {
            "positives": 2,
            "scan_date": "2018-03-26 19:29:08",
            "total": 67,
            "url": "http://027.ru/1.js",
        },
        {
            "positives": 4,
            "scan_date": "2018-01-14 22:39:41",
            "total": 66,
            "url": "http://027.ru/track.php",
        },
        {
            "positives": 2,
            "scan_date": "2018-01-09 22:19:43",
            "total": 66,
            "url": "http://027.ru/track.php?domain=027.ru&caf=1&toggle=answercheck"
            "&answer=yes&uid=MTUxNTUzNjM4MC4z"
            "MjkyOmIzOWFlYzQ2MTM2NzJjMTYwMGMyODU4N2VmNjAwYjM"
            "1MjA0OTE4NjlhOTNiZWMzYTI2ZjQ0N2Q5ZWU1ZDM3NWI6NWE1NTNmZmM1MDYyZA==",
        },
        {
            "positives": 3,
            "scan_date": "2018-01-08 17:40:54",
            "total": 66,
            "url": "http://027.ru/15.jpg:",
        },
        {
            "positives": 1,
            "scan_date": "2016-11-09 21:36:51",
            "total": 68,
            "url": "http://027.ru/testing",
        },
        {
            "positives": 2,
            "scan_date": "2015-02-18 08:54:52",
            "total": 62,
            "url": "http://027.ru/index.html",
        },
    ],
    "dns_records": [
        {"ttl": 3599, "type": "A", "value": "46.38.62.7"},
        {
            "expire": 604800,
            "minimum": 86400,
            "refresh": 10800,
            "retry": 3600,
            "rname": "root.example.com",
            "serial": 2017011500,
            "ttl": 3599,
            "type": "SOA",
            "value": "colocation0421.tel.ru",
        },
        {"ttl": 3599, "type": "TXT", "value": "v=spf1 ip4:46.38.62.5 a mx ~all"},
        {"ttl": 3599, "type": "NS", "value": "46.38.48.122"},
        {"ttl": 3599, "type": "NS", "value": "46.38.52.208"},
        {"priority": 10, "ttl": 3599, "type": "MX", "value": "mail.027.ru"},
        {"priority": 20, "ttl": 3599, "type": "MX", "value": "mail.027.ru"},
    ],
    "dns_records_date": 1564031431,
    "domain_siblings": [],
    "resolutions": [
        {"ip_address": "185.53.177.31", "last_resolved": "2018-09-03 10:58:50"},
        {"ip_address": "46.38.62.7", "last_resolved": "2019-07-30 06:20:22"},
        {"ip_address": "62.210.11.121", "last_resolved": "2016-01-18 00:00:00"},
        {"ip_address": "90.156.201.11", "last_resolved": "2013-05-03 00:00:00"},
        {"ip_address": "90.156.201.14", "last_resolved": "2013-05-07 00:00:00"},
        {"ip_address": "90.156.201.25", "last_resolved": "2016-09-08 00:00:00"},
        {"ip_address": "90.156.201.27", "last_resolved": "2013-04-01 00:00:00"},
        {"ip_address": "90.156.201.64", "last_resolved": "2016-11-09 00:00:00"},
        {"ip_address": "90.156.201.71", "last_resolved": "2013-05-01 00:00:00"},
        {"ip_address": "90.156.201.83", "last_resolved": "2016-12-22 00:00:00"},
        {"ip_address": "90.156.201.97", "last_resolved": "2013-06-20 00:00:00"},
    ],
    "response_code": 1,
    "subdomains": ["www.027.ru", "test.027.ru"],
    "undetected_downloaded_samples": [
        {
            "date": "2018-01-14 22:34:24",
            "positives": 0,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb9" "2427ae41e4649b934ca495991b7852b855",
            "total": 70,
        }
    ],
    "undetected_referrer_samples": [
        {
            "date": "2019-07-23 01:20:15",
            "positives": 0,
            "sha256": "3cc0709135e9053bb600192bb12965f" "8bc0909516e838ea33fdc2e2726d5ffa3",
            "total": 72,
        },
        {
            "date": "2019-07-22 05:49:06",
            "positives": 0,
            "sha256": "2a0ad2403e6b19ba9f164aaaf317981afc" "623069c3462f7b8ff93576e5adcda3",
            "total": 72,
        },
        {
            "date": "2019-07-17 15:57:17",
            "positives": 0,
            "sha256": "9a56215073d0b518fb2d57d77bca5bb2" "5a94aa63377d28a6342049027fd5b93b",
            "total": 70,
        },
        {
            "date": "2019-07-11 13:08:50",
            "positives": 0,
            "sha256": "15ebccfa8959f0510cbd366af6a5248f" "a711393d2331e0d81cb2dd6fc58188a3",
            "total": 70,
        },
        {
            "date": "2018-03-04 16:38:06",
            "positives": 0,
            "sha256": "ce08cf22949b6b6fcd4e61854ce810a" "4f9ee04529340dd077fa354d759dc7a95",
            "total": 66,
        },
        {
            "date": "2018-03-04 16:38:02",
            "positives": 0,
            "sha256": "05b475ad2a6876d9b00508e5400ad5c9" "7fa6b385bff5518f264219a4082676d8",
            "total": 61,
        },
        {
            "positives": 0,
            "sha256": "b8f5db667431d02291eeec61cf9f0c3d7" "af00798d0c2d676fde0efb0cedb7741",
            "total": 53,
        },
        {
            "positives": 0,
            "sha256": "b318ecd0296b550f52da74ed2a0b263" "a40d055f6520220f48bd03db370367522",
            "total": 61,
        },
    ],
    "undetected_urls": [],
    "verbose_msg": "Domain found in dataset",
    "whois": "domain: 027.RU\n"
    "nserver: ns1.nevstruev.ru.\n"
    "nserver: ns2.nevstruev.ru.\n"
    "state: REGISTERED, DELEGATED, VERIFIED\n"
    "registrar: RU-CENTER-RU\n"
    "created: 2005-12-08T21:00:00Z\n"
    "paid-till: 2019-12-08T21:00:00Z\n"
    "source: TCI\n"
    "Last updated on 2019-07-12T18:31:33Z",
    "whois_timestamp": 1562956563,
}


def test_virustotal_scan_domain():
    vt: VirusTotalScanDomainAction = VirusTotalScanDomainAction()
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://www.virustotal.com/vtapi/v2/domain/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&domain=027.ru",
            json=domain_results,
        )

        results: dict = vt.run({"domain": "027.ru"})

        assert results == domain_results
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert (
            history[0].url == "https://www.virustotal.com/vtapi/v2/domain/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            f'&{urllib.parse.urlencode({"domain": "027.ru"})}'
        )
