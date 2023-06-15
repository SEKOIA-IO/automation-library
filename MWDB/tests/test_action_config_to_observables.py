from collections import defaultdict

import pytest

from mwdb_module.action_config_to_observables import ConfigToObservablesAction
from tests.data import trigger_config_result


@pytest.fixture
def action():
    action = ConfigToObservablesAction()
    return action


def test_run(action):
    arguments = {"config": trigger_config_result}
    res = action.run(arguments)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    numbers = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        numbers[item["type"]] += 1
        if item["type"] == "file":
            assert "SHA-256" in item["hashes"]
            assert "SHA-1" in item["hashes"]

    assert numbers["file"] == 1
    assert numbers["ipv4-addr"] == 4
    assert numbers["domain-name"] == 1


def test_get_indicators_from_config_avemaria(action):
    config = {
        "c2": [{"host": "linuxpro1.warzonedns.com"}],
        "type": "avemaria",
        "drop_name": "",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_config_agenttesla(action):
    config = {
        "email": "info1@vitiren.website",
        "email_to": "info1@vitiren.website",
        "exfiltration_method": "smtp",
        "type": "agenttesla",
        "strings": {"in-blob": "ddbd2ba3100fea488483ddf0c5c5bfd0f1f46d895ca792c50b4ddb83525b05e5"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    config = {
        "exfiltration_method": "http",
        "key": ".tmp",
        "type": "agenttesla",
        "url": "http://myservepanel.com/webpanel/inc/3e9c944ce6d747.php",
        "strings": {"in-blob": "1e9b1063832db53b7f7d92b61da078bc5efc5a1f3f097880b5ae6cc2828d6e1b"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_config_azorult(action):
    config = {
        "mutex_suffix": "%",
        "type": "azorult",
        "cnc": "http://192.169.6.107/index.php",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_config_brushaloader(action):
    config = {
        "type": "brushaloader",
        "url": "https://derikaosos.info",
        "data": {"id": "golo"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_config_danabot(action):
    config = {
        "rsa_key": "BgIAAACkAABSU0ExAAQAAAEAAQDb3iEc2TuS6DvGew/JNXVqU",
        "urls": [
            "209.182.218.222",
            "185.227.109.40",
            "185.136.165.128",
            "161.129.65.197",
            "217.182.56.71",
            "110.236.210.87",
            "218.2.138.4",
            "167.214.156.174",
            "202.195.34.6",
            "185.181.8.49",
        ],
        "campaign_id": 31,
        "campaign_const": 545345335,
        "type": "danabot",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 10
    for item in res:
        assert item["type"] == "ipv4-addr"


def test_get_indicators_from_config_dridex(action):
    config = {
        "c2": [
            "188.166.156.241:443",
            "53.34.187.1:9989",
            "179.2.5.133:40178",
            "250.142.179.185:38651",
        ],
        "type": "dridex",
        "botnet": 40300,
        "RC4_key": [
            "ufeUtu7KZliEHxgBBUQDwRPwFH2qG167dw",
            "Tab5jYa8MfcljzYQ8fBSjHf17uhcO2ZnZVfGucXybIMSLjnJHqC5NOvUJbU9XTiYXOSlDZdy",
        ],
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 4
    for item in res:
        assert item["type"] == "ipv4-addr"
        assert item["x_inthreat_history"][0]["value"]["ports"][0] in [
            443,
            9989,
            40178,
            38651,
        ]


def test_get_indicators_from_config_emotet(action):
    config = {
        "urls": [
            {"cnc": "173.73.87.96", "port": 80},
            {"cnc": "71.222.233.135", "port": 443},
            {"cnc": "bad.com", "port": 443},
        ],
        "public_key": "-----BEGIN PUBLIC KEY-----\nMHwwDQYJKoZIhvcNAQAB\n-----END PUBLIC KEY-----",
        "type": "emotet",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 3
    ip = domain = 0
    for item in res:
        if item["type"] == "ipv4-addr":
            ip += 1
        else:
            domain += 1

    assert domain == 1
    assert ip == 2


def test_get_indicators_from_config_emotet_doc(action):
    config = {
        "type": "emotet_doc",
        "urls": [
            "http://kobo.nhanhwebvn.com/wp-admin/Cy4bJWG2PW/",
            "http://khoshrougallery.com/cgi-bin/fINL/",
            "http://legal.dailynotebook.org/wp-includes/K3601365/",
            "http://gatelen-002-site1.htempurl.com/6jfdf/yLv61/",
            "http://blog.prodigallovers.com/wp-content/SO10/",
        ],
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 5


def test_get_indicators_from_config_emotet_spam(action):
    config = {
        "type": "emotet_spam",
        "urls": [
            {"cnc": "51.77.113.100", "port": 7080},
            {"cnc": "178.250.54.208", "port": 8080},
            {"cnc": "45.55.82.2", "port": 8080},
        ],
        "hdr_const": 502300417,
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3


def test_get_indicators_from_config_emotet_upnp(action):
    config = {
        "urls": [
            {"cnc": "195.159.28.229", "port": 7080},
            {"cnc": "103.38.12.139", "port": 443},
            {"cnc": "198.46.150.196", "port": 7080},
        ],
        "type": "emotet_upnp",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3


def test_get_indicators_from_config_evil_pony(action):
    config = {
        "type": "evil-pony",
        "urls": [
            {"url": "http://twereptale.com/d2/about.php"},
            {"url": "http://charovalso.ru/d2/about.php"},
            {"url": "http://verectert.ru/d2/about.php"},
        ],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3


def test_get_indicators_from_config_formbook(action):
    config = {
        "decoy_domains": [
            "golermo.info",
            "noirmistpapillons.com",
            "oratechacademy.com",
            "qqhzs.com",
            "sol.events",
        ],
        "type": "formbook",
        "urls": [{"url": "www.sindomac.com/d80/"}],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "url"
    assert res[0]["value"].startswith("http://")


def test_get_indicators_from_get2(action):
    config = {"url": "https://integer-ms-home.com/ir2ask", "type": "get2"}
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_guloader(action):
    config = {
        "urls": [{"url": "https://drive.google.com/uc?export=download&id=1-P8YW9VNDeShDWDpZ6FKWJCaPKjRbCFg"}],
        "key": "73a8c5b2eb3f44aeb5e358fa8bd87998f61eea866f716982381539ce520b5a6c7a",
        "type": "guloader",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_hawkeye(action):
    config = {
        "AntiDebugger": False,
        "AntiVirusKiller": False,
        "BotKiller": False,
        "ClipboardLogger": True,
        "Delivery": 0,
        "DisableCommandPrompt": False,
        "DisableRegEdit": False,
        "DisableTaskManager": False,
        "Disablers": False,
        "EmailPassword": "GraceIn2019",
        "EmailPort": 587,
        "EmailSSL": True,
        "EmailServer": "mail.privateemail.com",
        "EmailUsername": "export@alasevtakstil.com",
        "ExecutionDelay": 10,
        "FTPPassword": None,
        "FTPPort": 0,
        "FTPSFTP": False,
        "FTPServer": None,
        "FTPUsername": None,
        "FakeMessageIcon": 0,
        "FakeMessageShow": False,
        "FakeMessageText": None,
        "FakeMessageTitle": None,
        "FileBinder": False,
        "FileBinderFiles": None,
        "HideFile": False,
        "HistoryCleaner": False,
        "Install": False,
        "InstallFileName": None,
        "InstallFolder": None,
        "InstallLocation": 0,
        "InstallStartup": False,
        "InstallStartupPersistance": False,
        "KeyStrokeLogger": True,
        "LogInterval": 10,
        "MeltFile": False,
        "Mutex": "c791e5f0-8192-4865-80eb-f2a01ee9db8a",
        "PanelSecret": None,
        "PanelURL": None,
        "PasswordStealer": True,
        "ProcessElevation": False,
        "ProcessProtection": False,
        "ProxySecret": None,
        "ProxyURL": None,
        "ScreenshotLogger": False,
        "SystemInfo": False,
        "Version": "9.0.1.6",
        "WebCamLogger": False,
        "WebsiteBlocker": False,
        "WebsiteBlockerSites": None,
        "WebsiteVisitor": False,
        "WebsiteVisitorSites": None,
        "WebsiteVisitorVisible": False,
        "ZoneID": False,
        "type": "hawkeye",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "email-addr"


def test_get_indicators_from_icedid(action):
    config = {
        "binary_id": 548174735,
        "domains": [
            {"cnc": "gfthwards.com"},
            {"cnc": "gfthwards.eu"},
            {"cnc": "gfthwards.net"},
            {"cnc": "presifered.com"},
            {"cnc": "coujtried.com"},
        ],
        "type": "icedid",
        "minor_version": 2,
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 5


def test_get_indicators_from_isfb(action):
    config = {
        "xcookie": 4,
        "compilation_date": "Feb 19 2020",
        "public_key": {
            "n": "87075865895834340437100804690786285758066352364935900596721029607075292594179594038562",
            "e": 65537,
        },
        "domains": [
            {"cnc": "vv.malorun.at/api1"},
            {"cnc": "g8.farihon.at/api1"},
            {"cnc": "g4xp7aanksu6qgci.onion/api1"},
            {"cnc": "deem.dianer.at/api1"},
            {"cnc": "dn.ramtool.at/api1"},
        ],
        "ips": [
            "193.183.98.66",
            "51.15.98.97",
            "94.247.43.254",
            "195.10.195.195",
            "8.8.8.8",
        ],
        "dga_base_url": "constitution.org/usdeclar.txt",
        "dga_crc": 1320669898,
        "dga_tld": [".com", ".ru", ".org"],
        "dga_season": 10,
        "tor32_dll": "api10.dianer.at/jvassets/xI/t34.dat",
        "tor64_dll": "api10.dianer.at/jvassets/xI/t64.dat",
        "ip_service": "curlmyip.net",
        "server": 730,
        "key": "U7yKaYwFde7YtppY",
        "timer": 120,
        "configtimeout": 600,
        "configfailtimeout": 600,
        "tasktimeout": 240,
        "sendtimeout": 300,
        "knockertimeout": 300,
        "bctimeout": 10,
        "botnet": 3000,
        "dga_seed": 1,
        "exe_type": "worker",
        "ssl": True,
        "dga_count": 5,
        "dga_lsa_seed": 3988359472,
        "version": "2.17.119",
        "type": "isfb",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 5
    for item in res:
        assert item["type"] == "url"


def test_get_indicators_from_kpot(action):
    config = {
        "url": [
            "http://trynda.xyz/arDbOgfFC3xCNKJR",
            "http://trynda1.xyz/arDbOgfFC3xCNKJR",
            "http://trynda2.xyz/arDbOgfFC3xCNKJR",
        ],
        "key": "WTVpmUbiXE2hcnWZ",
        "type": "kpot",
        "strings": {"in-blob": "db8eebb1683b86acad2ee3b0f70d766d31bfe99f06ea067d35c2d70701e4a578"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3

    config = {
        "url": "http://zeleron.duckdns.org/Z6O0f04bowOkpUs1",
        "type": "kpot",
        "key": "X4Tr16oqtY9Jcu3N",
        "strings": {"in-blob": "77a4c50e74ac788b0fdf39dc4155ddb3eac775fd46f5c8c8dfcf55c8eb7e2f8e"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_kronos(action):
    config = {
        "urls": [{"url": "http://jevuknz34ronf3pl.onion/kpanel/connect.php"}],
        "cnc": "jevuknz34ronf3pl.onion",
        "type": "kronos",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_legionloader(action):
    config = {
        "stealer": "http://legion17.top/legion17/welcome",
        "stealer_data": "HorseHours",
        "drops": [
            "http://lolupdate4.top/test/eu/1.exe",
            "http://lolupdate4.top/test/eu/2.exe",
        ],
        "user_agent": "cock",
        "cnc": "http://lolupdate4.top/gate1.php?a={bbed3e55656ghf02-0b41-11e3-8249}id=2",
        "type": "legionloader",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 4


def test_get_indicators_from_lokibot(action):
    config = {
        "urls": [
            {"url": "http://23.95.132.48/~main/.isuoxiso/w.php/JLlbjCEJ9CtbN"},
            {"url": "kbfvzoboss.bid/alien/fre.php"},
            {"url": "alphastand.trade/alien/fre.php"},
        ],
        "cc_key": "f86af04da7d691e6be98fd3db48b9b7b3779389495f95125",
        "cc_iv": "4cf8799b5abda2c0",
        "type": "lokibot",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3
    for item in res:
        assert item["value"].startswith("http")


def test_get_indicators_from_mirai(action):
    config = {
        "cncs": [{"host": "chuyucnc.duckdns.org", "port": 39799}],
        "table_key": "0xdeaddaad",
        "variant": "UNSTABLE",
        "type": "mirai",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "domain-name"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [39799]


def test_get_indicators_from_mirai2(action):
    config = {
        "cncs": [{"host": "194.180.224.124", "port": 26663}],
        "table_key": "0xdeadbeef",
        "variant": "UNST",
        "type": "mirai",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "ipv4-addr"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [26663]


def test_get_indicators_from_mirai3(action):
    config = {
        "port": 23,
        "type": "mirai",
        "domains": [{"domain": "cnc.mydigitalcloud.ddns.net"}],
        "variant": "MIRAI",
        "table_key": "0xdeadbeef",
        "table_entries": {"in-blob": "b12e44fcf9209916f74834baf9ed7c1cdfed0e5e99f2c8445047e9f96ad2c307"},
        "table_key_effective_decr": ["0x22", '"'],
        "table_key_effective_encr": ["0x22", '"'],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "domain-name"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [23]


def test_get_indicators_from_mirai4(action):
    config = {
        "ips": [{"ip": "205.185.126.121"}],
        "port": 55555,
        "type": "mirai",
        "table_key": "0xdedefbaf",
        "table_key_effective_decr": ["0x54", "T"],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "ipv4-addr"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [55555]


def test_get_indicators_from_nanocore(action):
    config = {
        "BypassUAC": "00",
        "Group": "AA Back",
        "EnableDebugMode": "00",
        "Version": "1.2.2.0",
        "Mutex": "4e8ec7d6fae06548b581ccd3777c6455",
        "Domain2": "79.134.225.62",
        "Domain1": "meeti.ddns.net",
        "ClearAccessControl": "00",
        "RequestElevation": "00",
        "RestartDelay": 5000,
        "RunOnStartup": "01",
        "PreventSystemSleep": "01",
        "UseCustomDNS": "01",
        "PrimaryDNSServer": "8.8.8.8",
        "ConnectDelay": 4000,
        "SetCriticalProcess": "00",
        "type": "nanocore",
        "Port": 1012,
        "ClearZoneIdentifier": "01",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_netwire(action):
    config = {
        "filename": "HostId-%Rand%",
        "dir-path": "%AppData%\\Logs\\",
        "reg-key": False,
        "mutex": "UQrgsndM",
        "urls": [{"cnc": "nybenlord.duckdns.org", "port": 1972}],
        "flags": [96, 1, 75],
        "password": "Password",
        "type": "netwire",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_njrat(action):
    config = {
        "c2": ["216.170.123.10:5556"],
        "drop_name": "serverrrr.exe",
        "type": "njrat",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "ipv4-addr"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [5556]


def test_get_indicators_from_njrat2(action):
    config = {
        "id": "NYAN CAT",
        "cncs": [{"host": "211.209.164.138", "port": "3333"}],
        "type": "njrat",
        "version": "0.7NC",
        "registry": "54bd74517f10492a",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "ipv4-addr"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [3333]


def test_get_indicators_from_ostap(action):
    config = {
        "type": "ostap",
        "cmd_header": "RedSparrow",
        "urls": [{"url": "https://185.159.82.20/t-34/x644.php?min=up"}],
        "binary": "ca5babac91882be1c901c2183fa28f1f8d315424ec5bd2589155bd63c1d4608f",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_phorpiex(action):
    config = {
        "cncs": [{"host": "220.181.87.80", "port": 5050}],
        "cnc_url": "http://220.181.87.80/t.exe",
        "directory": "%s\\M-50504502105437043020493029585030",
        "type": "phorpiex",
        "encryption_key": "trk",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_pony(action):
    config = {
        "drops": [{"url": "http://acousticallysound.com.au/images/shit.exe"}],
        "type": "pony",
        "urls": [{"url": "http://acousticallysound.com.au/images/gate.php"}],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_pushdo(action):
    config = {
        "seskey": "51e82a97f5772b9700000000000000000000000000000000",
        "dga_tld": ".kz",
        "file_name": "tulgenaqixtu",
        "cfgkey": {
            "e": 65537,
            "d": "89120872268701834330362071328732427804837942381170827096082023126434649570181119156373776",
            "n": "13538976833272860724406441976520948356619527653766324745933999883257180410016133533034928",
        },
        "trnsl_tbl": {
            "order": "1d13b8730ae4c80d574d7920c15f1cdf5b34b2335529603e7e4f58303cbfb7311987682c83d63fefc46d8",
            "tags": [
                35090,
                56801,
                11312,
                39373,
                56627,
                35392,
                6400,
                29970,
                61197,
                54154,
                44252,
                31506,
                51764,
                61264,
                37119,
                26602,
            ],
        },
        "domains": [
            {"cnc": "crcsi.org"},
            {"cnc": "t-tre.com"},
            {"cnc": "abart.pl"},
            {"cnc": "medisa.info"},
        ],
        "privkey": {
            "e": 65537,
            "d": "225649668340162519145004102068755343106685517733208583674790925535348507782949486825834486941",
            "n": "134635855007367361773544554235979778961970582444294345851190576172706984291434454826153630469",
        },
        "type": "pushdo",
        "unk1": 3439523813,
        "unk2": 294222654,
        "pubkey": {
            "e": 65537,
            "n": "115880579792338937911521072322839432593251740588157277308157762754242612651648178025452468379",
        },
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 4


def test_get_indicators_from_quasarrat(action):
    config = {
        "encryption_key": "DonBo$$",
        "hosts": ["kilohugs.xyz:4580"],
        "install_name": "Skype.exe",
        "log_directory": "Logs",
        "mutex": "QSR_MUTEX_Xi1eG9ZUMB5uAwGz6F",
        "startup_key": "Skype",
        "subdirectory": "AppData",
        "type": "quasarrat",
        "version": "1.3.0.0",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "domain-name"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [4580]


def test_get_indicators_from_raccoon(action):
    config = {
        "urls": {"url": "https://drive.google.com/uc?export=download&id=1infq5NdVX48gNHfBOjNoHfIFGAtPoJPc"},
        "config_id": "63f77434d3f9a874e67e5de356d92f4737c4694a",
        "rc4_key": "19e13280086d90194cdeef6a93af7ecc",
        "type": "raccoon",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_ramnit(action):
    config = {
        "dga_domain_no": 50,
        "harcoded_domain": "okjndyeu3017uhe.com",
        "rc4_key": "fenquyidh",
        "config_magic": "demetra",
        "config_type": 7,
        "dga_seed": 742724187,
        "rsa_key": "MIGJAoGAh4vwKBmjAcGgbLNRtS9XXRwfDLQ1P0UDJwEmRfUPSP7aIInbuy77pnGwOM4NXjAvZrAP6akx44d9FtNFV/Kmd",
        "md5_magic": "45Bn99gT",
        "type": "ramnit",
        "port": 443,
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_ramnit_list(action):
    config = {
        "dga_domain_no": 50,
        "harcoded_domain": ["okjndyeu3017uhe.com", "oyyndyeu3017uhe.com"],
        "rc4_key": "fenquyidh",
        "config_magic": "demetra",
        "config_type": 7,
        "dga_seed": 742724187,
        "rsa_key": "MIGJAoGAh4vwKBmjAcGgbLNRtS9XXRwfDLQ1P0UDJwEmRfUPSP7aIInbuy77pnGwOM4NXjAvZrAP6akx44d9FtNFV/Kmd",
        "md5_magic": "45Bn99gT",
        "type": "ramnit",
        "port": 443,
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_remcos(action):
    config = {
        "c2": [{"host": "185.140.53.154:8760", "password": ""}],
        "type": "remcos",
        "raw_cfg": {"in-blob": "927642849b4c8d25fda8b462000975277a6e53946ab626b784113ff00a13a0ab"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "ipv4-addr"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [8760]


def test_get_indicators_from_smokeloader(action):
    config = {
        "rc4_key_resp": "0xb9adf00d",
        "smk_magic": 2018,
        "sample_id": "",
        "domains": [
            {"cnc": "http://185.35.137.147/mlp/"},
            {"cnc": "http://j5cool.xyz/wp/"},
        ],
        "type": "smokeloader",
        "rc4_key_req": "0xd9adbeef",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_systembc(action):
    config = {
        "host": ["senblog89.xyz", "rexstat35.club"],
        "type": "systembc",
        "port": ["4044"],
        "dns": ["5.132.191.104", "92.163.33.248", "206.189.120.27"],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_trickbot(action):
    config = {
        "version": 1000501,
        "botnet": "ono32",
        "urls": [
            {"cnc": "5.182.210.226", "port": 443},
            {"cnc": "5.182.210.120", "port": 449},
        ],
        "public_key": {
            "t": "ecdsa_pub_p384",
            "x": "3742067904504044416825214432099211423284466927075923804",
            "y": "4932519521119379107882309939233205684582235529120728741",
        },
        "type": "trickbot",
        "raw_cfg": {"in-blob": "bcdde2a38a84978c2387fa4002d0f3ef648a97dcacb34d414cc9a0a840b701b7"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2
    for item in res:
        assert item["type"] == "ipv4-addr"
        assert item["x_inthreat_history"][0]["value"]["ports"][0] in [443, 449]


def test_get_indicators_from_vjworm(action):
    config = {
        "type": "vjworm",
        "campaign_name": "CITACION",
        "urls": [{"url": "http://primerenvio2020.duckdns.org:7974/Vre"}],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_wshrat(action):
    config = {
        "type": "wshrat",
        "c2": ["http://pastebin.com/raw/CNRZ8Tmk:9999"],
        "installdir": "%appdata%",
        "runAsAdmin": "false",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_zloader(action):
    config = {
        "botnet": "\u0006",
        "rc4key": "q23Cud3xsNf3",
        "urls": [
            {"url": "http://marchadvertisingnetwork.com/post.php"},
            {"url": "http://marchadvertisingnetwork2.com/post.php"},
            {"url": "http://marchadvertisingnetwork3.com/post.php"},
        ],
        "type": "zloader",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3


def test_get_indicators_from_dbatloader(action):
    config = {
        "cncs": [{"url": "https://cdn.discordapp.com/attachments/751567034013450323/753153585528963072/Dtlk674"}],
        "key": "Seo091",
        "type": "dbatloader",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_dharma(action):
    config = {
        "emails": ["admin@fentex.world", "admin@fentex.net"],
        "type": "dharma",
        "raw_cfg": {"in-blob": "732f2fb4dfc05ce31e3051055249a478464b508b644899bc7c0f31777f83ec30"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2


def test_get_indicators_from_dharma_no_email(action):
    config = {
        "type": "dharma",
        "strings": {"in-blob": "4cb48d0fd9e77b74bcd077d5c20457bee782834c5bd4f814798b7d6460abe221"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 0


def test_get_indicators_from_sodinokibi(action):
    config = {
        "pk": "U1v/e5rsm+MBAyMWauKbSQoNySoEV1oLxrYMgzIi4SI=",
        "pid": "$2a$10$QattBzSnFe.5XRJJ1p0cN.Co.kQ6PbwK3Q6eZtQUfTXEQhSWGiqhe",
        "sub": "4920",
        "dbg": False,
        "et": 1,
        "wipe": False,
        "wht": {
            "fld": [
                "programdata",
                "$windows.~ws",
                "windows.old",
            ],
            "fls": ["ntuser.dat", "bootsect.bak", "boot.ini"],
            "ext": ["theme", "sys", "lnk", "msc", "exe"],
        },
        "wfld": ["backup"],
        "dmn": "rerekatu.com;comarenterprises.com;lapmangfpt.info.vn;tradiematepro.com.au;copystar.co.uk",
        "net": False,
        "nbody": "LQAtAC0APQA9AD0AIABXAGUAbABjAG8AbQBlAC4AIABBAGcAYQBpAG4ALgAgAD0APQA9AC",
        "nname": "{EXT}-readme.txt",
        "exp": False,
        "img": "QQBsAGwAIABvAGYAIAB5AG8AdQByACAAZgBpAGwAZQBzACAAYQByAGUAIABlAG4AYwByAHkA",
        "arn": False,
        "type": "sodinokibi",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 5


def test_get_indicators_from_config_emotet_wrong_domains(action):
    config = {
        "urls": [
            {"cnc": "not_a_domain", "port": 80},
            {"cnc": "1.2.3.4.5.6", "port": 443},
        ],
        "public_key": "-----BEGIN PUBLIC KEY-----\nMHwwDQYJKoZIhvcNAQAB\n-----END PUBLIC KEY-----",
        "type": "emotet",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 0


def test_get_indicators_from_config_revengerat(action):
    config = {
        "id": "Guest",
        "key": "Revenge-RAT",
        "mutex": "RV_MUTEX",
        "cncs": [{"host": "61.110.138.194", "port": "5050"}],
        "type": "revengerat",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [5050]


def test_get_indicators_from_config_amadey(action):
    config = {
        "key": "fd309d0cc5520f091e693d8563a81c12",
        "cncs": [{"host": "217.8.117.52"}],
        "type": "amadey",
        "raw_cfg": {"in-blob": "ecf8adeedee8d8158c5903b0a84a9875bdaa57ccde585247873e6c0af21c5cc8"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_config_orcusrat(action):
    config = {
        "type": "orcusrat",
        "raw_cfg": {"in-blob": "721cc5debedb833440684f4ee394ac7a7be90b0652c8a65348622cd86f96b6a2"},
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 0


def test_get_indicators_from_config_valak(action):
    config = {
        "js-payload": {"in-blob": "af1077125ad15df0edbdb95f478547e37ba34854509f8f3ac9c7576ab4728884"},
        "urls": [
            "http://pixel.buzzfeed.com",
            "http://event-reporting-dot-webylytics.appspot.com",
            "http://evs-hosted-14facd241e1c08.s3.amazonaws.com",
            "http://sodp399.com",
            "http://dhs331.com",
            "http://xow301.com",
        ],
        "type": "valak",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 6


def test_get_indicators_from_config_hancitor(action):
    config = {
        "type": "hancitor",
        "urls": [
            {"url": "http://varembacen.com/8/forum.php"},
            {"url": "http://twomplon.ru/8/forum.php"},
            {"url": "http://latiounitere.ru/8/forum.php"},
        ],
        "build": "1204_spk",
        "user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; Trident/7.0; rv:11.0) like Gecko",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3


def test_get_indicators_from_config_danabot_new_format(action):
    config = {
        "ips": [
            {"ip": "198.211.116.98"},
            {"ip": "165.227.38.61"},
            {"ip": "8.208.9.104"},
            {"ip": "134.209.237.20"},
        ],
        "type": "danabot",
        "urls": [
            {"url": "http://198.211.116.98:443"},
            {"url": "http://165.227.38.61:443"},
            {"url": "http://8.208.9.104:443"},
            {"url": "http://134.209.237.20:443"},
        ],
        "affid": 22,
        "timeout": 360000,
        "version": 1827,
        "embedded_hash": " F0CDE8332809AAECCF99C00772B539AB",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 8
    for item in res:
        assert item["type"] in ["ipv4-addr", "url"]


def test_get_indicators_from_config_cobaltstrike(action):
    config = {
        "Port": 80,
        "type": "cobaltstrike",
        "urls": [
            {"url": "180.101.217.175/s/ref=nb_sb_noss_1/167-3294888-0262949/field-keywords=books"},
            {"url": "27.221.28.182/s/ref=nb_sb_noss_1/167-3294888-0262949/field-keywords=books"},
            {"url": "123.125.46.41/s/ref=nb_sb_noss_1/167-3294888-0262949/field-keywords=books"},
        ],
        "Jitter": 0,
        "MaxDNS": "Not Found",
        "SpawnTo": "00000000000000000000000000000000",
        "domains": [
            {"domain": "180.101.217.175"},
            {"domain": "27.221.28.182"},
            {"domain": "123.125.46.41"},
        ],
        "C2Server": "180.101.217.175,/s/ref=nb_sb_noss_1/167-3294888-0262949/field-keywords=books,27.221.28.182,",
        "DNS_Idle": "Not Found",
        "KillDate": 0,
        "PipeName": "Not Found",
        "SSH_Host": "Not Found",
        "SSH_Port": "Not Found",
        "DNS_Sleep": "Not Found",
        "PublicKey": "30819f300d06092a864886f70d010101050003818d003081890281810086310c1deea5",
        "SleepTime": 5000,
        "UserAgent": "Not Found",
        "Watermark": 426352781,
        "BeaconType": ["HTTP"],
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 6
    for item in res:
        assert item["type"] in ["ipv4-addr", "url"]
        if item["type"] == "ipv4-addr":
            assert item["x_inthreat_history"][0]["value"]["ports"] == [80]


def test_get_indicators_from_config_cryptbot(action):
    config = {
        "type": "cryptbot",
        "urls": [
            {"url": "http://peoldb01.top/download.php?file=lv.exe"},
            {"url": "http://kiylip13.top/index.php"},
            {"url": "http://mormbl01.top/index.php"},
        ],
        "domains": [
            {"domain": "peoldb01.top"},
            {"domain": "kiylip13.top"},
            {"domain": "mormbl01.top"},
        ],
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 6
    for item in res:
        assert item["type"] in ["domain-name", "url"]


def test_get_indicators_from_config_qbot(action):
    config = {
        "type": "qbot",
        "urls": [
            {"url": "105.198.236.101:443"},
            {"url": "136.232.34.70:443"},
            {"url": "http://foo.com:995"},
        ],
        "version": {"major": "402", "minor": 68},
        "botgroup": "obama59",
        "timestamp": "2021-06-11 08:04:34",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 5
    for item in res:
        assert item["type"] in ["url", "ipv4-addr"]
        if item["type"] == "ipv4-addr":
            assert item["x_inthreat_history"][0]["value"]["ports"] == [443]


def test_get_indicators_from_config_quasar(action):
    config = {
        "TAG": "test1",
        "type": "quasar",
        "urls": [{"url": "129.151.100.167:4782"}],
        "MUTEX": "e7f5e79a-e13e-454c-a27a-b2cccd20d1f3",
        "VERSION": "1.4.0",
        "STARTUPKEY": "SU",
        "INSTALLNAME": "System Unlocker.exe",
        "SUBDIRECTORY": "su",
        "ENCRYPTIONKEY": "61C214D616D9A80A18774D77EDBC99276EB630A1",
        "SERVERSIGNATURE": "1RFPniEqZjQmKOqpn322u5OUM510c2psQ+CXrYduJYqGuQhDF",
        "LOGDIRECTORYNAME": "windowslogs",
        "SERVERCERTIFICATESTR": "MIIE9DCCAtygAwIBAgIQAKSgz/UVffrJdWkMkDEtDTANBgkqhkiG9w0BAQ0FADAbMRkw",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 2
    for item in res:
        assert item["type"] in ["url", "ipv4-addr"]
        if item["type"] == "ipv4-addr":
            assert item["x_inthreat_history"][0]["value"]["ports"] == [4782]


def test_get_indicators_from_config_quasar2(action):
    config = {
        "TAG": "test1",
        "type": "quasar",
        "urls": [{"url": "jereshost.ddns.net", "port": "4782"}],
        "MUTEX": "e7f5e79a-e13e-454c-a27a-b2cccd20d1f3",
        "VERSION": "1.4.0",
        "STARTUPKEY": "SU",
        "INSTALLNAME": "System Unlocker.exe",
        "SUBDIRECTORY": "su",
        "ENCRYPTIONKEY": "61C214D616D9A80A18774D77EDBC99276EB630A1",
        "SERVERSIGNATURE": "1RFPniEqZjQmKOqpn322u5OUM510c2psQ+CXrYduJYqGuQhDF",
        "LOGDIRECTORYNAME": "windowslogs",
        "SERVERCERTIFICATESTR": "MIIE9DCCAtygAwIBAgIQAKSgz/UVffrJdWkMkDEtDTANBgkqhkiG9w0BAQ0FADAbMRkw",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 2
    for item in res:
        assert item["type"] in ["url", "domain-name"]
        if item["type"] == "domain-name":
            assert item["x_inthreat_history"][0]["value"]["ports"] == [4782]


def test_get_indicators_from_config_asyncrat(action):
    config = {
        "MTX": "AsyncMutex_6SI8OkPnk",
        "BDOS": "false",
        "anti": "false",
        "type": "asyncrat",
        "delay": "3",
        "group": "Default",
        "hosts": "127.0.0.1,176.98.41.49",
        "ports": "7707,8808,6606",
        "domains": [
            {"port": "7707", "domain": "127.0.0.1"},
            {"port": "8808", "domain": "127.0.0.1"},
            {"port": "6606", "domain": "127.0.0.1"},
            {"port": "7707", "domain": "176.98.41.49"},
            {"port": "8808", "domain": "176.98.41.49"},
            {"port": "6606", "domain": "176.98.41.49"},
        ],
        "install": "true",
        "version": "0.5.7B",
        "certificate": "MIIE8jCCAtqgAwIBAgIQAIde+cMmqR8d0+4JaRQLsTANBgkqhkiG9w0BAQ0FADAaMRgwFgYD",
        "install_file": "tempzz.exe",
        "install_folder": "%Temp%",
        "serversignature": "twP/louuoTQsYX29u/zANhxvCJvsS",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 6
    for item in res:
        assert item["type"] == "ipv4-addr"
        assert item["x_inthreat_history"][0]["value"]["ports"][0] in [7707, 8808, 6606]


def test_get_indicators_from_config_gozi(action):
    config = {
        "type": "gozi",
        "botnet": "8877",
        "server": "12",
        "timer1": "1",
        "timer2": "60",
        "domains": [
            {"domain": "37.120.222.65"},
            {"domain": "37.120.222.89"},
            {"domain": "37.120.222.9"},
            {"domain": "mureborufer.one"},
            {"domain": "pureborufer.one"},
            {"domain": "wureborufer.one"},
        ],
        "rsa_key": "00020000c45f16e09ea0716ae754c6d2bcccc13a9cf4ac695",
        "variant": "Gozi2RM3",
        "version": "250212",
        "exe_type": "loader",
        "bctimeout": "10",
        "directory": "/images/",
        "dga_season": "10",
        "ip_service": "api.wipmania.com ipinfo.io/ip api.wipmania.com curlmyip.net",
        "keyloglist": "notepad, iexplore, chrome, firefox, terminal, mstsc, edge, ",
        "dns_servers": "107.174.86.134 107.175.127.22",
        "sendtimeout": "300",
        "serpent_key": "30218409ILPAJDUR",
        "tasktimeout": "300",
        "configtimeout": "300",
        "knockertimeout": "300",
        "compilation_date": "Unknown",
        "configfailtimeout": "300",
        "first_stage_extension": ".avi",
        "second_stage_extension": ".crew",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 6


def test_get_indicators_from_config_xloader(action):
    config = {
        "keys": [
            "651b832bf53864df45c8defbf16f985c639edff7",
            "061b1dc66a930d2fc30b596edf6c594bf65e205a",
            "2b16727cb4f992fdc4447541750211338f22a0f3",
            "4465f6d81e7a12b63567f35ca52aad613fa0bb21",
            "1d6d95d0d96b3467dbbb9a5962d8a7906798cc3904",
            "dcb1537d7bfc3caa81831aef565ebbb351d84d3e",
            "7fa79702be7f88fca977bb58f2c596b746b54957",
            "5a3167032bab6fc68dc5a7d386bb65f6415959f2",
        ],
        "type": "xloader",
        "urls": [
            {"url": "http://www.bughtmisly.com/n64d/"},
            {"url": "http://www.hayominta.com/n64d/"},
            {"url": "http://www.dunstabzug.website/n64d/"},
            {"url": "http://www.fafmediagroup.com/n64d/"},
            {"url": "http://www.keepamericagreatagain-again.com/n64d/"},
        ],
        "domains": [{"domain": "www.bughtmisly.com"}],
        "variant": "gen.2",
        "version": "2.3",
        "decoy_domains": [
            {"domain": "hayominta.com"},
            {"domain": "dunstabzug.website"},
            {"domain": "fafmediagroup.com"},
            {"domain": "keepamericagreatagain-again.com"},
        ],
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 2
    for item in res:
        assert item["value"] in [
            "www.bughtmisly.com",
            "http://www.bughtmisly.com/n64d/",
        ]


def test_get_indicators_from_config_redlinestealer(action):
    config = {
        "key": "Gormand",
        "cncs": [{"host": "190.2.136.29", "port": "3279"}],
        "type": "redlinestealer",
    }

    res = action.extract_observables_from_config(config)
    assert len(res) == 1
    assert res[0]["type"] == "ipv4-addr"
    assert res[0]["value"] == "190.2.136.29"
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [3279]


def test_get_indicators_from_config_squirrel_waffle(action):
    config = {
        "cncs": [
            {"url": "alcorbogaindonesia.com/9poRAbODT"},
            {"url": "mediacionmelipilla.cl/4ugcVLVzG"},
            {"url": "escenachile.cl/qflR3r5quK"},
        ],
        "type": "SquirrelWaffle",
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 3


def test_get_indicators_from_config_redline(action):
    config = {
        "id": "R10K",
        "key": "Myological",
        "type": "redline",
        "urls": [{"url": "http://rilsiettauk.xyz:80"}],
        "domains": [{"domain": "rilsiettauk.xyz"}],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_config_warzone(action):
    config = {
        "ips": [{"ip": "91.193.75.247"}],
        "type": "warzone",
        "urls": [{"url": "http://91.193.75.247:9961"}],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 1


def test_get_indicators_from_config_tofsee(action):
    config = {
        "type": "tofsee",
        "domains": [
            {"port": 443, "domain": "patmushta.info"},
            {"port": 443, "domain": "ovicrush.cn"},
        ],
    }
    res = action.extract_observables_from_config(config)
    assert len(res) == 2
    assert res[0]["x_inthreat_history"][0]["value"]["ports"] == [443]
