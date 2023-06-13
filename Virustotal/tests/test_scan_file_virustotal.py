import time
from unittest.mock import patch

import requests_mock

from virustotal.action_virustotal_scanfile import VirusTotalScanFileAction

file_result: dict = {
    "scans": {
        "Bkav": {
            "detected": True,
            "version": "1.3.0.10239",
            "result": "DOS.EiracA.Trojan",
            "update": "20190808",
        },
        "TotalDefense": {
            "detected": True,
            "version": "37.1.62.1",
            "result": "the EICAR test string",
            "update": "20190808",
        },
        "MicroWorld-eScan": {
            "detected": True,
            "version": "14.0.297.0",
            "result": "EICAR-Test-File",
            "update": "20190808",
        },
        "FireEye": {
            "detected": True,
            "version": "29.7.0.0",
            "result": "EICAR-Test-File (not a virus)",
            "update": "20190808",
        },
        "CAT-QuickHeal": {
            "detected": True,
            "version": "14.00",
            "result": "EICAR.TestFile",
            "update": "20190807",
        },
        "ALYac": {
            "detected": True,
            "version": "1.1.1.5",
            "result": "EICAR-Test-File (not a virus)",
            "update": "20190808",
        },
        "Malwarebytes": {
            "detected": False,
            "version": "2.1.1.1115",
            "result": None,
            "update": "20190808",
        },
        "K7AntiVirus": {
            "detected": True,
            "version": "11.59.31671",
            "result": "Trojan ( 000139291 )",
            "update": "20190808",
        },
        "Alibaba": {
            "detected": True,
            "version": "0.3.0.5",
            "result": "Virus:Any/EICAR_Test_File.534838ff",
            "update": "20190527",
        },
        "K7GW": {
            "detected": True,
            "version": "11.59.31672",
            "result": "Trojan ( 000139291 )",
            "update": "20190808",
        },
        "Arcabit": {
            "detected": True,
            "version": "1.0.0.856",
            "result": "EICAR-Test-File (not a virus)",
            "update": "20190808",
        },
        "Baidu": {
            "detected": True,
            "version": "1.0.0.2",
            "result": "Win32.Test.Eicar.a",
            "update": "20190318",
        },
        "Cyren": {
            "detected": True,
            "version": "6.2.0.1",
            "result": "EICAR_Test_File",
            "update": "20190808",
        },
        "Symantec": {
            "detected": True,
            "version": "1.10.0.0",
            "result": "EICAR Test String",
            "update": "20190808",
        },
        "ESET-NOD32": {
            "detected": True,
            "version": "19819",
            "result": "Eicar test file",
            "update": "20190808",
        },
        "APEX": {
            "detected": True,
            "version": "5.48",
            "result": "EICAR Anti-Virus Test File",
            "update": "20190806",
        },
        "ClamAV": {
            "detected": True,
            "version": "0.101.3.0",
            "result": "Eicar-Test-Signature",
            "update": "20190807",
        },
        "Kaspersky": {
            "detected": True,
            "version": "15.0.1.13",
            "result": "EICAR-Test-File",
            "update": "20190808",
        },
        "BitDefender": {
            "detected": True,
            "version": "7.2",
            "result": "EICAR-Test-File (not a virus)",
            "update": "20190808",
        },
        "NANO-Antivirus": {
            "detected": True,
            "version": "1.0.134.24859",
            "result": "Marker.Dos.EICAR-Test-File.dyb",
            "update": "20190808",
        },
        "ViRobot": {
            "detected": True,
            "version": "2014.3.20.0",
            "result": "EICAR-test",
            "update": "20190808",
        },
        "AegisLab": {
            "detected": True,
            "version": "4.2",
            "result": "Test.File.EICAR.y!c",
            "update": "20190808",
        },
        "Tencent": {
            "detected": True,
            "version": "1.0.0.1",
            "result": "EICAR.TEST.NOT-A-VIRUS",
            "update": "20190808",
        },
        "Ad-Aware": {
            "detected": True,
            "version": "3.0.5.370",
            "result": "EICAR-Test-File (not a virus)",
            "update": "20190808",
        },
        "Sophos": {
            "detected": True,
            "version": "4.98.0",
            "result": "EICAR-AV-Test",
            "update": "20190808",
        },
        "Comodo": {
            "detected": True,
            "version": "31292",
            "result": "Malware@#xgi4rmucsjhj",
            "update": "20190808",
        },
        "DrWeb": {
            "detected": True,
            "version": "7.0.41.7240",
            "result": "EICAR Test File (NOT a Virus!)",
            "update": "20190808",
        },
        "VIPRE": {
            "detected": True,
            "version": "77000",
            "result": "EICAR (v)",
            "update": "20190808",
        },
        "McAfee-GW-Edition": {
            "detected": True,
            "version": "v2017.3010",
            "result": "EICAR test file",
            "update": "20190808",
        },
        "CMC": {
            "detected": False,
            "version": "1.1.0.977",
            "result": None,
            "update": "20190321",
        },
        "Emsisoft": {
            "detected": True,
            "version": "2018.12.0.1641",
            "result": "EICAR-Test-File (not a virus) (B)",
            "update": "20190808",
        },
        "SentinelOne": {
            "detected": True,
            "version": "1.0.31.22",
            "result": "DFI - Malicious COM",
            "update": "20190807",
        },
        "Avast-Mobile": {
            "detected": True,
            "version": "190807-00",
            "result": "Eicar",
            "update": "20190807",
        },
        "Jiangmin": {
            "detected": True,
            "version": "16.0.100",
            "result": "EICAR-Test-File",
            "update": "20190808",
        },
        "Webroot": {
            "detected": True,
            "version": "1.0.0.403",
            "result": "W32.EICAR.TestVirus.Gen",
            "update": "20190808",
        },
        "Avira": {
            "detected": True,
            "version": "8.3.3.8",
            "result": "Eicar-Test-Signature",
            "update": "20190808",
        },
        "Antiy-AVL": {
            "detected": True,
            "version": "3.0.0.1",
            "result": "TestFile/Win32.EICAR",
            "update": "20190808",
        },
        "Kingsoft": {
            "detected": False,
            "version": "2013.8.14.323",
            "result": None,
            "update": "20190808",
        },
        "Endgame": {
            "detected": True,
            "version": "3.0.13",
            "result": "eicar",
            "update": "20190802",
        },
        "Microsoft": {
            "detected": True,
            "version": "1.1.16200.1",
            "result": "Virus:DOS/EICAR_Test_File",
            "update": "20190808",
        },
        "SUPERAntiSpyware": {
            "detected": True,
            "version": "5.6.0.1032",
            "result": "NotAThreat.EICAR[TestFile]",
            "update": "20190802",
        },
        "ZoneAlarm": {
            "detected": True,
            "version": "1.0",
            "result": "EICAR-Test-File",
            "update": "20190808",
        },
        "GData": {
            "detected": True,
            "version": "A:25.23018B:26.15738",
            "result": "EICAR_TEST_FILE",
            "update": "20190808",
        },
        "TACHYON": {
            "detected": True,
            "version": "2019-08-08.02",
            "result": "EICAR-Test-File",
            "update": "20190808",
        },
        "AhnLab-V3": {
            "detected": True,
            "version": "3.16.0.24856",
            "result": "EICAR_Test_File",
            "update": "20190808",
        },
        "McAfee": {
            "detected": True,
            "version": "6.0.6.653",
            "result": "EICAR test file",
            "update": "20190808",
        },
        "MAX": {
            "detected": True,
            "version": "2018.9.12.1",
            "result": "malware (ai score=99)",
            "update": "20190808",
        },
        "VBA32": {
            "detected": True,
            "version": "4.0.0",
            "result": "EICAR-Test-File",
            "update": "20190807",
        },
        "Zoner": {
            "detected": True,
            "version": "1.0.0.1",
            "result": "EICAR.Test.File-NoVirus.250",
            "update": "20190807",
        },
        "TrendMicro-HouseCall": {
            "detected": True,
            "version": "10.0.0.1040",
            "result": "Eicar_test_file",
            "update": "20190808",
        },
        "Rising": {
            "detected": True,
            "version": "25.0.0.24",
            "result": "EICAR-Test-File (CLASSIC)",
            "update": "20190808",
        },
        "Yandex": {
            "detected": True,
            "version": "5.5.2.24",
            "result": "EICAR_test_file",
            "update": "20190807",
        },
        "Ikarus": {
            "detected": True,
            "version": "0.1.5.2",
            "result": "EICAR-Test-File",
            "update": "20190807",
        },
        "MaxSecure": {
            "detected": True,
            "version": "1.0.0.1",
            "result": "Virus.COM.Eicar.TestFile",
            "update": "20190803",
        },
        "F-Prot": {
            "detected": True,
            "version": "4.7.1.166",
            "result": "EICAR_Test_File",
            "update": "20190808",
        },
        "Panda": {
            "detected": False,
            "version": "4.6.4.2",
            "result": None,
            "update": "20190807",
        },
        "Qihoo-360": {
            "detected": True,
            "version": "1.0.0.1120",
            "result": "qex.eicar.gen.gen",
            "update": "20190808",
        },
    },
    "scan_id": "131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267-1565249201",
    "sha1": "cf8bd9dfddff007f75adf4c2be48005cea317c62",
    "resource": "131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267-1565249201",
    "response_code": 1,
    "scan_date": "2019-08-08 07:26:41",
    "permalink": "https://www.virustotal.com/file/131f95c51cc819465fa1797f6ccacf9d494aaaff46"
    "fa3eac73ae63ffbdfd8267/analysis/1565249201/",
    "verbose_msg": "Scan finished, information embedded",
    "total": 57,
    "positives": 53,
    "sha256": "131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267",
    "md5": "69630e4574ec6798239b091cda43dca0",
}


@patch.object(time, "sleep")
def test_virustotal_scan_file(mock_sleep):
    vt: VirusTotalScanFileAction = VirusTotalScanFileAction()
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://www.virustotal.com/vtapi/v2/file/scan",
            status_code=200,
            json={"scan_id": "131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267-1565249201"},
        )

        mock.get(
            "https://www.virustotal.com/vtapi/v2/file/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267-1565249201",
            json=file_result,
        )

        results = vt.run({"file": "tests/eicar.txt"})

        mock_sleep.assert_called()
        assert results == file_result
        assert mock.call_count == 2

        history = mock.request_history
        assert history[0].method == "POST"
        assert (
            history[0].url == "https://www.virustotal.com/vtapi/v2/file/scan"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        )

        assert history[1].method == "GET"
        assert (
            history[1].url == "https://www.virustotal.com/vtapi/v2/file/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267"
            "-1565249201"
        )
