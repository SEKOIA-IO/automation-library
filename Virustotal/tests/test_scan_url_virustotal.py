import urllib.parse

import pytest
import requests_mock

from virustotal.action_virustotal_scanurl import VirusTotalScanURLAction
from virustotal.errors import RequestLimitError

url_results: dict = {
    "filescan_id": None,
    "permalink": "https://www.virustotal.com/url"
    "/9317a6262af44bfe12a03e29f05745ebd466f641297ef04a548b427efdbbfde4"
    "/analysis/1565316883/",
    "positives": 0,
    "resource": "https://www.virustotal.com/gui/home/upload",
    "response_code": 1,
    "scan_date": "2019-08-09 02:14:43",
    "scan_id": "9317a6262af44bfe12a03e29f05745ebd466f641297ef04a548b427efdbbfde4-1565316883",
    "scans": {
        "ADMINUSLabs": {"detected": False, "result": "clean site"},
        "AegisLab WebGuard": {"detected": False, "result": "clean site"},
        "AlienVault": {"detected": False, "result": "clean site"},
        "Antiy-AVL": {"detected": False, "result": "clean site"},
        "AutoShun": {"detected": False, "result": "unrated site"},
        "Avira": {"detected": False, "result": "clean site"},
        "BADWARE.INFO": {"detected": False, "result": "clean site"},
        "Baidu-International": {"detected": False, "result": "clean site"},
        "BitDefender": {"detected": False, "result": "clean site"},
        "Blueliv": {"detected": False, "result": "clean site"},
        "CLEAN MX": {"detected": False, "result": "clean site"},
        "CRDF": {"detected": False, "result": "clean site"},
        "Comodo Site Inspector": {"detected": False, "result": "clean site"},
        "CyRadar": {"detected": False, "result": "clean site"},
        "CyberCrime": {"detected": False, "result": "clean site"},
        "DNS8": {"detected": False, "result": "clean site"},
        "Dr.Web": {"detected": False, "result": "clean site"},
        "ESET": {"detected": False, "result": "clean site"},
        "ESTsecurity-Threat Inside": {"detected": False, "result": "clean site"},
        "Emsisoft": {"detected": False, "result": "clean site"},
        "EonScope": {"detected": False, "result": "clean site"},
        "Forcepoint ThreatSeeker": {"detected": False, "result": "clean site"},
        "Fortinet": {"detected": False, "result": "clean site"},
        "FraudScore": {"detected": False, "result": "clean site"},
        "FraudSense": {"detected": False, "result": "clean site"},
        "G-Data": {"detected": False, "result": "clean site"},
        "Google Safebrowsing": {"detected": False, "result": "clean site"},
        "K7AntiVirus": {"detected": False, "result": "clean site"},
        "Kaspersky": {"detected": False, "result": "clean site"},
        "Malc0de Database": {
            "detail": "http://malc0de.com/database/index.php?search=www.virustotal.com",
            "detected": False,
            "result": "clean site",
        },
        "Malekal": {"detected": False, "result": "clean site"},
        "Malware Domain Blocklist": {"detected": False, "result": "clean site"},
        "MalwareDomainList": {
            "detail": "http://www.malwaredomainlist.com/mdl.php?search=www.virustotal.com",
            "detected": False,
            "result": "clean site",
        },
        "MalwarePatrol": {"detected": False, "result": "clean site"},
        "Malwarebytes hpHosts": {"detected": False, "result": "clean site"},
        "Malwared": {"detected": False, "result": "clean site"},
        "Netcraft": {"detected": False, "result": "unrated site"},
        "NotMining": {"detected": False, "result": "unrated site"},
        "Nucleon": {"detected": False, "result": "clean site"},
        "OpenPhish": {"detected": False, "result": "clean site"},
        "Opera": {"detected": False, "result": "clean site"},
        "PhishLabs": {"detected": False, "result": "unrated site"},
        "Phishtank": {"detected": False, "result": "clean site"},
        "Quttera": {"detected": False, "result": "clean site"},
        "Rising": {"detected": False, "result": "clean site"},
        "SCUMWARE.org": {"detected": False, "result": "clean site"},
        "SecureBrain": {"detected": False, "result": "clean site"},
        "Segasec": {"detected": False, "result": "unrated site"},
        "Sophos": {"detected": False, "result": "unrated site"},
        "Spam404": {"detected": False, "result": "clean site"},
        "Spamhaus": {"detected": False, "result": "clean site"},
        "StopBadware": {"detected": False, "result": "unrated site"},
        "Sucuri SiteCheck": {"detected": False, "result": "clean site"},
        "Tencent": {"detected": False, "result": "clean site"},
        "ThreatHive": {"detected": False, "result": "clean site"},
        "Trustwave": {"detected": False, "result": "clean site"},
        "URLQuery": {"detected": False, "result": "clean site"},
        "URLhaus": {"detected": False, "result": "clean site"},
        "VX Vault": {"detected": False, "result": "clean site"},
        "Virusdie External Site Scan": {"detected": False, "result": "clean site"},
        "Web Security Guard": {"detected": False, "result": "clean site"},
        "Yandex Safebrowsing": {
            "detail": "http://yandex.com/infected?l10n=en" "&url=https://www.virustotal.com/gui/home/upload",
            "detected": False,
            "result": "clean site",
        },
        "ZCloudsec": {"detected": False, "result": "clean site"},
        "ZDB Zeus": {"detected": False, "result": "clean site"},
        "ZeroCERT": {"detected": False, "result": "clean site"},
        "Zerofox": {"detected": False, "result": "clean site"},
        "ZeusTracker": {
            "detail": "https://zeustracker.abuse.ch/monitor.php?host=www.virustotal.com",
            "detected": False,
            "result": "clean site",
        },
        "desenmascara.me": {"detected": False, "result": "clean site"},
        "malwares.com URL checker": {"detected": False, "result": "clean site"},
        "securolytics": {"detected": False, "result": "clean site"},
        "zvelo": {"detected": False, "result": "clean site"},
    },
    "total": 71,
    "url": "https://www.virustotal.com/gui/home/upload",
    "verbose_msg": "Scan finished, scan information embedded in this object",
}


def test_virustotal_scan_url():
    vt: VirusTotalScanURLAction = VirusTotalScanURLAction()
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
    url: str = "https://www.virustotal.com/gui/home/upload"

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://www.virustotal.com/vtapi/v2/url/report"
            f"?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            f"&resource={url}",
            json=url_results,
        )

        results = vt.run({"url": url})

        assert results == url_results
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert (
            history[0].url == f"https://www.virustotal.com/vtapi/v2/url/report"
            f"?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            f'&{urllib.parse.urlencode({"resource": url})}'
            f"&scan=1"
        )


def test_virustotal_scan_url_no_scans():
    vt: VirusTotalScanURLAction = VirusTotalScanURLAction()
    vt.sleep_multiplier = 0
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
    url: str = "https://www.virustotal.com/gui/home/upload"

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://www.virustotal.com/vtapi/v2/url/report"
            f"?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            f"&resource={url}",
            json={},
            status_code=204,
        )

        with pytest.raises(RequestLimitError):
            vt.run({"url": url})
