import requests_mock

from virustotal.action_virustotal_scanhash import VirusTotalScanHashAction

hash_results: dict = {
    "scans": {
        "Bkav": {
            "detected": False,
            "version": "1.3.0.10239",
            "result": None,
            "update": "20190607",
        },
        "MicroWorld-eScan": {
            "detected": False,
            "version": "14.0.297.0",
            "result": None,
            "update": "20190608",
        },
        "FireEye": {
            "detected": True,
            "version": "29.7.0.0",
            "result": "Trojan.GenericKD.32011371",
            "update": "20190607",
        },
        "CAT-QuickHeal": {
            "detected": True,
            "version": "14.00",
            "result": "Trojan.Generic",
            "update": "20190606",
        },
        "McAfee": {
            "detected": True,
            "version": "6.0.6.653",
            "result": "Artemis!DAA573CE4C09",
            "update": "20190607",
        },
        "Cylance": {
            "detected": True,
            "version": "2.3.1.101",
            "result": "Unsafe",
            "update": "20190608",
        },
        "SUPERAntiSpyware": {
            "detected": False,
            "version": "5.6.0.1032",
            "result": None,
            "update": "20190604",
        },
        "Trustlook": {
            "detected": False,
            "version": "1.0",
            "result": None,
            "update": "20190608",
        },
        "Alibaba": {
            "detected": True,
            "version": "0.3.0.5",
            "result": "Trojan:Win32/Generic.48dbe8a2",
            "update": "20190527",
        },
        "K7GW": {
            "detected": True,
            "version": "11.48.31164",
            "result": "Riskware ( 0040eff71 )",
            "update": "20190608",
        },
        "K7AntiVirus": {
            "detected": True,
            "version": "11.48.31164",
            "result": "Riskware ( 0040eff71 )",
            "update": "20190607",
        },
        "TrendMicro": {
            "detected": True,
            "version": "10.0.0.1040",
            "result": "TROJ_GEN.R002C0WET19",
            "update": "20190607",
        },
        "Baidu": {
            "detected": False,
            "version": "1.0.0.2",
            "result": None,
            "update": "20190318",
        },
        "Babable": {
            "detected": False,
            "version": "9107201",
            "result": None,
            "update": "20190424",
        },
        "F-Prot": {
            "detected": True,
            "version": "4.7.1.166",
            "result": "W32/AutoIt5.ACE",
            "update": "20190608",
        },
        "Symantec": {
            "detected": True,
            "version": "1.9.0.0",
            "result": "Trojan.Gen.NPE",
            "update": "20190607",
        },
        "TotalDefense": {
            "detected": False,
            "version": "37.1.62.1",
            "result": None,
            "update": "20190607",
        },
        "TrendMicro-HouseCall": {
            "detected": False,
            "version": "10.0.0.1040",
            "result": None,
            "update": "20190607",
        },
        "Avast": {
            "detected": True,
            "version": "18.4.3895.0",
            "result": "Win32:Malware-gen",
            "update": "20190606",
        },
        "ClamAV": {
            "detected": False,
            "version": "0.101.2.0",
            "result": None,
            "update": "20190607",
        },
        "Kaspersky": {
            "detected": True,
            "version": "15.0.1.13",
            "result": "HEUR:Trojan.Win32.Generic",
            "update": "20190607",
        },
        "BitDefender": {
            "detected": True,
            "version": "7.2",
            "result": "Trojan.GenericKD.32011371",
            "update": "20190607",
        },
        "NANO-Antivirus": {
            "detected": True,
            "version": "1.0.134.24826",
            "result": "Trojan.Win32.Mlw.fqtwhu",
            "update": "20190608",
        },
        "AegisLab": {
            "detected": True,
            "version": "4.2",
            "result": "Trojan.Win32.Generic.4!c",
            "update": "20190607",
        },
        "Tencent": {
            "detected": True,
            "version": "1.0.0.1",
            "result": "Win32.Trojan.Generic.Edxm",
            "update": "20190608",
        },
        "Endgame": {
            "detected": False,
            "version": "3.0.12",
            "result": None,
            "update": "20190522",
        },
        "Emsisoft": {
            "detected": True,
            "version": "2018.4.0.1029",
            "result": "Trojan.GenericKD.32011371 (B)",
            "update": "20190607",
        },
        "Comodo": {
            "detected": True,
            "version": "30987",
            "result": "Malware@#3mvap7284untd",
            "update": "20190608",
        },
        "F-Secure": {
            "detected": True,
            "version": "12.0.86.52",
            "result": "Trojan.TR/AD.Swotter.qdbcy",
            "update": "20190607",
        },
        "DrWeb": {
            "detected": False,
            "version": "7.0.34.11020",
            "result": None,
            "update": "20190607",
        },
        "Zillya": {
            "detected": False,
            "version": "2.0.0.3828",
            "result": None,
            "update": "20190607",
        },
        "Invincea": {
            "detected": True,
            "version": "6.3.6.26157",
            "result": "heuristic",
            "update": "20190525",
        },
        "McAfee-GW-Edition": {
            "detected": True,
            "version": "v2017.3010",
            "result": "BehavesLike.Downloader.cc",
            "update": "20190607",
        },
        "CMC": {
            "detected": False,
            "version": "1.1.0.977",
            "result": None,
            "update": "20190321",
        },
        "Sophos": {
            "detected": True,
            "version": "4.98.0",
            "result": "Mal/Generic-S",
            "update": "20190608",
        },
        "Cyren": {
            "detected": True,
            "version": "6.2.0.1",
            "result": "W32/AutoIt.EKFH-0576",
            "update": "20190607",
        },
        "Jiangmin": {
            "detected": False,
            "version": "16.0.100",
            "result": None,
            "update": "20190529",
        },
        "Avira": {
            "detected": True,
            "version": "8.3.3.8",
            "result": "TR/AD.Swotter.qdbcy",
            "update": "20190608",
        },
        "Fortinet": {
            "detected": True,
            "version": "5.4.247.0",
            "result": "Malicious_Behavior.SB",
            "update": "20190608",
        },
        "Antiy-AVL": {
            "detected": True,
            "version": "3.0.0.1",
            "result": "GrayWare/Autoit.ShellCode.a",
            "update": "20190607",
        },
        "Kingsoft": {
            "detected": False,
            "version": "2013.8.14.323",
            "result": None,
            "update": "20190608",
        },
        "Arcabit": {
            "detected": True,
            "version": "1.0.0.846",
            "result": "Trojan.Generic.D1E8746B",
            "update": "20190608",
        },
        "ViRobot": {
            "detected": True,
            "version": "2014.3.20.0",
            "result": "Trojan.Win32.Z.Sonbokli.1305600",
            "update": "20190607",
        },
        "ZoneAlarm": {
            "detected": True,
            "version": "1.0",
            "result": "HEUR:Trojan.Win32.Generic",
            "update": "20190607",
        },
        "Avast-Mobile": {
            "detected": False,
            "version": "190606-00",
            "result": None,
            "update": "20190606",
        },
        "Microsoft": {
            "detected": True,
            "version": "1.1.16000.6",
            "result": "Trojan:Win32/Tiggre!rfn",
            "update": "20190607",
        },
        "TACHYON": {
            "detected": False,
            "version": "2019-06-07.02",
            "result": None,
            "update": "20190607",
        },
        "AhnLab-V3": {
            "detected": True,
            "version": "3.15.2.24317",
            "result": "Win-Trojan/AutoInj.Exp",
            "update": "20190607",
        },
        "VBA32": {
            "detected": False,
            "version": "4.0.0",
            "result": None,
            "update": "20190607",
        },
        "MAX": {
            "detected": False,
            "version": "2018.9.12.1",
            "result": None,
            "update": "20190608",
        },
        "Ad-Aware": {
            "detected": False,
            "version": "3.0.5.370",
            "result": None,
            "update": "20190607",
        },
        "Malwarebytes": {
            "detected": True,
            "version": "2.1.1.1115",
            "result": "Trojan.MalPack.Generic",
            "update": "20190608",
        },
        "Zoner": {
            "detected": False,
            "version": "1.0",
            "result": None,
            "update": "20190608",
        },
        "ESET-NOD32": {
            "detected": True,
            "version": "19488",
            "result": "a variant of Generik.LCEHGH",
            "update": "20190608",
        },
        "Rising": {
            "detected": True,
            "version": "25.0.0.24",
            "result": "PUF.Pack-AutoIt!1.B8E7 (CLASSIC)",
            "update": "20190608",
        },
        "Yandex": {
            "detected": False,
            "version": "5.5.2.24",
            "result": None,
            "update": "20190607",
        },
        "Ikarus": {
            "detected": True,
            "version": "0.1.5.2",
            "result": "Trojan.Autoit",
            "update": "20190607",
        },
        "GData": {
            "detected": True,
            "version": "A:25.22296B:25.15266",
            "result": "Trojan.GenericKD.32011371",
            "update": "20190608",
        },
        "AVG": {
            "detected": True,
            "version": "18.4.3895.0",
            "result": "Win32:Malware-gen",
            "update": "20190606",
        },
        "Panda": {
            "detected": True,
            "version": "4.6.4.2",
            "result": "Trj/CI.A",
            "update": "20190607",
        },
        "Qihoo-360": {
            "detected": True,
            "version": "1.0.0.1120",
            "result": "Win32/Trojan.045",
            "update": "20190608",
        },
    },
    "scan_id": "5eb7e00e8f3ecf41439ec117436de6314155f258f3052e6aaecb28a03198b677-1559951323",
    "sha1": "36437528c1e97d21ae198407b788f32eeed29e49",
    "resource": "36437528c1e97d21ae198407b788f32eeed29e49",
    "response_code": 1,
    "scan_date": "2019-06-07 23:48:43",
    "permalink": "https://www.virustotal.com/file/5eb7e00e8f3ecf41439ec117436de6314155f258f3052e6aaecb28a03198b677"
    "/analysis/1559951323/",
    "verbose_msg": "Scan finished, information embedded",
    "total": 61,
    "positives": 39,
    "sha256": "5eb7e00e8f3ecf41439ec117436de6314155f258f3052e6aaecb28a03198b677",
    "md5": "f69ede7cf7c4cb5e95f04610353b1837",
}


def test_virustotal_check_hash():
    hashed: str = "36437528c1e97d21ae198407b788f32eeed29e49"

    vt: VirusTotalScanHashAction = VirusTotalScanHashAction()
    vt.module.configuration = {"apikey": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://www.virustotal.com/vtapi/v2/file/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=36437528c1e97d21ae198407b788f32eeed29e49",
            json=hash_results,
        )

        results = vt.run({"hash": hashed})

        assert results == hash_results
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert (
            history[0].url == "https://www.virustotal.com/vtapi/v2/file/report"
            "?apikey=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            "&resource=36437528c1e97d21ae198407b788f32eeed29e49"
        )
