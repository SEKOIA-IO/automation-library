import json
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
import requests_mock
from osintcollector.trigger_osint import OSINTTrigger


@pytest.fixture(autouse=True)
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


@pytest.fixture
def ssh_source():
    source = {
        "name": "blocklist.de ssh",
        "identity": "blocklist.de",
        "url": "https://lists.blocklist.de/lists/ssh.txt",
        "frequency": 172800,
        "global_format": "line",
        "fields": ["ipv4-addr"],
        "ignore": "#",
        "tags": ["scanner", "scanner:ssh"],
        "tags_valid_for": 30,
    }
    results = """#####8.8.8.8  Will be ignored
1.10.185.247
1.163.232.194
1.179.137.10
1.179.182.82"""

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], text=results)

        yield source


def get_name_and_bundle(storage, send_event):
    (name, event, directory), kwargs = send_event.call_args

    assert kwargs == {"remove_directory": True}

    filepath = storage / directory / event["bundle_path"]
    with filepath.open("r") as fd:
        return name, json.load(fd)


@patch.object(OSINTTrigger, "send_event")
def test_init_source(send_event, ssh_source, symphony_storage):
    trigger = OSINTTrigger(data_path=symphony_storage)
    trigger._configuration = {"collection_sources": [ssh_source]}
    trigger._init_sources()

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: blocklist.de ssh: 4 observables"

    observables = set()
    for obj in bundle["objects"]:
        if obj["type"] == "ipv4-addr":
            observables.add(obj["value"])

    assert observables == {"1.10.185.247", "1.163.232.194", "1.179.137.10", "1.179.182.82"}


@patch.object(OSINTTrigger, "_run")
@patch.object(OSINTTrigger, "log")
def test_init_source_unknown(log, run, symphony_storage):
    trigger = OSINTTrigger(data_path=symphony_storage)
    trigger._configuration = {"collection_sources": [{"global_format": "unknown", "name": "bad"}]}
    trigger._init_sources()
    assert not run.called
    assert log.called


@patch.object(OSINTTrigger, "send_event")
def test_ssh(send_event, ssh_source, symphony_storage):
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(ssh_source)

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: blocklist.de ssh: 4 observables"

    observables = set()
    for obj in bundle["objects"]:
        if obj["type"] == "ipv4-addr":
            observables.add(obj["value"])

    assert observables == {"1.10.185.247", "1.163.232.194", "1.179.137.10", "1.179.182.82"}


@patch.object(OSINTTrigger, "send_event")
def test_ssh_tags(send_event, ssh_source, symphony_storage):
    trigger = OSINTTrigger(data_path=symphony_storage)
    trigger._run(ssh_source)
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    for obj in bundle["objects"]:
        if obj["type"] != "identity":
            assert "x_inthreat_tags" in obj
            assert len(obj["x_inthreat_tags"]) == 2

            tags = set()
            for tag in obj["x_inthreat_tags"]:
                tags.add(tag["name"])
                assert tag["valid_from"]
                assert tag["valid_until"]

            assert tags == {"scanner", "scanner:ssh"}


@pytest.fixture
def ssh_download_source():
    source = {
        "name": "nothink hash",
        "identity": "nothink",
        "url": "http://www.nothink.org/honeypot_ssh_download.php",
        "frequency": 86400,
        "global_format": "html",
        "fields": ["_", "file:hashes.SHA-256", "_", "_", "_", "_"],
    }

    results = """<!DOCTYPE html>
<html lang="en">
<head>

<title>NoThink!</title>

<link href="http://www.nothink.org/css/bootstrap.css" rel="stylesheet" type="text/css">
<link href="http://www.nothink.org/css/bootstrap-responsive.css" rel="stylesheet" type="text/css">
<link href="http://www.nothink.org/css/nothink.css" rel="stylesheet" type="text/css">
</head>
<body>

<div class="navbar navbar-inverse navbar-fixed-top">
    <div class="navbar-inner">
        <div class="container">
                  <button type="button" class="btn btn-navbar" data-toggle="collapse" data-target=".nav-collapse">
                <span class="icon-bar"></span>
                <span class="icon-bar"></span>
                <span class="icon-bar"></span>
            </button>
            <a class="brand" href="index.php">NoThink!</a>
            <div class="nav-collapse collapse">
                <ul class="nav">
                    <li class="active"><a href="http://www.nothink.org/index.php">Home</a></li>
                    <li><a href="http://www.nothink.org/honeypots.php">Honeypots</a></li>
                    <li><a href="http://www.nothink.org/codes.php">Codes</a></li>
                    <li><a href="http://www.nothink.org/about.php">About</a></li>
                </ul>
            </div>
        </div>
    </div>
</div>

<div class="container">

<h1>Honeypot SSH - Latest files downloaded</h1><i>This page is updated daily. Last update: 2019-10-08 22:06:07 UTC</i><br/><br/><table class="table table-bordered table-striped">
<thead>
<tr>
<th>Datetime</th>
<th>Filename (shasum) - VirusTotal analysis link</th>
<th>Drop URL</th>
<th>VT scan date (first analysis)</th>
<th>VT results (first analysis)</th>
</tr>
</thead>
<tbody>
<tr><td>2019-10-07</td><td><a href='https://www.virustotal.com/file/05bd9140c3a9daf64abb6c2b45148dbe9192efc02710de99a340ed6f1aa6bb7d/analysis/1570153138/'>05bd9140c3a9daf64abb6c2b45148dbe9192efc02710de99a340ed6f1aa6bb7d</a></td><td>-</td><td>2019-10-04</td><td>30/57</td></tr>
<tr><td>2019-10-07</td><td><a href='https://www.virustotal.com/file/269224036227440b37198cbbfd70e563845ce9cae0c26ab54349488c67b638ff/analysis/1567721588/'>269224036227440b37198cbbfd70e563845ce9cae0c26ab54349488c67b638ff</a></td><td>-</td><td>2019-09-05</td><td>15/56</td></tr>
<tr><td>2019-10-03</td><td><a href='https://www.virustotal.com/file/2ccf742f7f8ecf04ce35f721dad364f723a4c9140060aa78c5105a00910ba719/analysis/1569981918/'>2ccf742f7f8ecf04ce35f721dad364f723a4c9140060aa78c5105a00910ba719</a></td><td>-</td><td>2019-10-02</td><td>30/56</td></tr>
<tr><td>2019-10-03</td><td><a href='https://www.virustotal.com/file/47c3b1349b6da4ebb7f9b9575d6e779a8cb8b2805feaabd4b780dd548245014a/analysis/1570062614/'>47c3b1349b6da4ebb7f9b9575d6e779a8cb8b2805feaabd4b780dd548245014a</a></td><td>-</td><td>2019-10-03</td><td>27/56</td></tr>
</tbody></table></div>

</body>
</html>"""  # noqa: E501

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], text=results)

        yield source


@patch.object(OSINTTrigger, "send_event")
def test_ssh_download(send_event, ssh_download_source, symphony_storage):
    # This test has two objectives:
    #
    # * test an HTML source
    # * test more complex observables such as Files
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(ssh_download_source)

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: nothink hash: 4 observables"

    observables = set()
    for obj in bundle["objects"]:
        if obj["type"] == "file":
            observables.add(obj["hashes"]["SHA-256"])

    assert observables == {
        "05bd9140c3a9daf64abb6c2b45148dbe9192efc02710de99a340ed6f1aa6bb7d",
        "269224036227440b37198cbbfd70e563845ce9cae0c26ab54349488c67b638ff",
        "2ccf742f7f8ecf04ce35f721dad364f723a4c9140060aa78c5105a00910ba719",
        "47c3b1349b6da4ebb7f9b9575d6e779a8cb8b2805feaabd4b780dd548245014a",
    }


@pytest.fixture
def hashes_source():
    source = {
        "name": "hashes",
        "identity": "hashes",
        "url": "https://someurl.com/hashes.txt",
        "frequency": 172800,
        "global_format": "line",
        "fields": [
            "file:hashes.MD5",
            "file:hashes.SHA-1",
            "file:hashes.SHA-256",
            "context:tag",
        ],
        "separator": " ",
        "ignore": "#",
    }
    results = "942faeae9f5b5442bc89438c437b7493 88eba5d205d85c39ced484a3aa7241302fd815e3 2b83c69cf32c5f8f43ec2895ec9ac730bf73e1b2f37e44a3cf8ce814fb51f120 foo"  # noqa: E501

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], text=results)

        yield source


@patch.object(OSINTTrigger, "send_event")
def test_combined_observable(send_event, hashes_source, symphony_storage):
    # This test builds an observables with several fields taken from the source
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(hashes_source)

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: hashes: 1 observable"
    assert len(bundle["objects"]) == 2

    for obj in bundle["objects"]:
        if obj["type"] == "file":
            assert obj["hashes"]["MD5"] == "942faeae9f5b5442bc89438c437b7493"
            assert obj["hashes"]["SHA-1"] == "88eba5d205d85c39ced484a3aa7241302fd815e3"
            assert obj["hashes"]["SHA-256"] == "2b83c69cf32c5f8f43ec2895ec9ac730bf73e1b2f37e44a3cf8ce814fb51f120"


@patch.object(OSINTTrigger, "send_event")
def test_combined_observable_cache(send_event, hashes_source, symphony_storage):
    # This test builds an observables with several fields taken from the source
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(hashes_source)
    send_event.assert_called_once()

    # Call it a second time an make sure send_event is not called another time
    trigger._run(hashes_source)
    send_event.assert_called_once()


@patch.object(OSINTTrigger, "send_event")
def test_observable_cache(send_event, ssh_source, symphony_storage):
    # Test the observable cache
    trigger = OSINTTrigger(data_path=symphony_storage)

    # Run the trigger once, it should send an event with all observables
    trigger._run(ssh_source)
    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)
    assert len(bundle["objects"]) == 5  # 4 observable + 1 identity

    # Run the trigger another time with the same data, it should net send an event
    trigger._run(ssh_source)
    send_event.assert_called_once()  # Old call

    # Run the trigger with updated data, only new observables should be returned
    results = """1.10.185.247
1.163.232.194
1.179.137.10
1.179.182.82
1.156.8.47"""

    with requests_mock.Mocker() as mock:
        mock.get(ssh_source["url"], text=results)

        trigger._run(ssh_source)
        assert send_event.call_count == 2
        name, bundle = get_name_and_bundle(symphony_storage, send_event)
        assert len(bundle["objects"]) == 2  # 1 new observable + 1 identity

        for obj in bundle["objects"]:
            if obj["type"] == "ipv4-addr":
                assert obj["value"] == "1.156.8.47"


@pytest.fixture
def amazon_ranges_source():
    source = {
        "name": "Amazon AWS IP Ranges",
        "identity": "Amazon AWS",
        "url": "https://ip-ranges.amazonaws.com/ip-ranges.json",
        "frequency": 172800,
        "global_format": "json",
        "fields": ["ipv4-addr"],
        "item_format": ["$.ip_prefix"],
        "iterate_over": "prefixes",
        "cache_results": False,
    }
    results = {
        "syncToken": "1571157189",
        "createDate": "2019-10-15-16-33-09",
        "prefixes": [
            {
                "ip_prefix": "13.248.118.0/24",
                "region": "eu-west-1",
                "service": "AMAZON",
            },
            {"ip_prefix": "18.208.0.0/13", "region": "us-east-1", "service": "AMAZON"},
            {"ip_prefix": "52.93.81.52/31", "region": "eu-west-1", "service": "AMAZON"},
            {
                "ipv6_prefix": "2600:1f01:4840::/47",
                "region": "sa-east-1",
                "service": "AMAZON",
            },
        ],
    }

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], json=results)

        yield source


@patch.object(OSINTTrigger, "send_event")
def test_osint_amazon(send_event, symphony_storage, amazon_ranges_source):
    trigger = OSINTTrigger(data_path=symphony_storage)
    trigger._run(amazon_ranges_source)
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert len(bundle["objects"]) == 4  # 1 identity + 3 ipv4
    ipv4_results = set()

    for obj in bundle["objects"]:
        if obj["type"] == "ipv4-addr":
            ipv4_results.add(obj["value"])

    assert ipv4_results == {"13.248.118.0/24", "18.208.0.0/13", "52.93.81.52/31"}


@patch.object(OSINTTrigger, "send_event")
def test_osint_amazon_nocache(send_event, symphony_storage, amazon_ranges_source):
    trigger = OSINTTrigger(data_path=symphony_storage)

    # Call it once, it should send an event with all data
    trigger._run(amazon_ranges_source)
    assert send_event.call_count == 1

    # Calling it a second time should also send an event because cache is disabled
    trigger._run(amazon_ranges_source)
    assert send_event.call_count == 2


@pytest.fixture
def et_tor_source():
    source = {
        "name": "Emerging Threats Tor Rules",
        "identity": "Emerging Threats",
        "url": "http://rules.emergingthreats.net/open/snort-2.9.0/rules/emerging-tor.rules",
        "frequency": 172800,
        "global_format": "regex",
        "fields": ["ipv4-addr"],
        "item_format": [r"(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b)"],
    }
    results = """
#  VERSION 3850

#  Updated 2019-10-17 00:30:01

alert tcp [103.15.28.215,103.208.220.122,103.208.220.226,103.234.220.195,103.249.28.195,103.28.53.138,103.68.109.167,103.75.190.11,104.200.20.46,104.218.63.72] any -> $HOME_NET any (msg:"ET TOR Known Tor Exit Node TCP Traffic group 1"; flags:S; reference:url,doc.emergingthreats.net/bin/view/Main/TorRules; threshold: type limit, track by_src, seconds 60, count 1; classtype:misc-attack; flowbits:set,ET.TorIP; sid:2520000; rev:3850; metadata:affected_product Any, attack_target Any, deployment Perimeter, tag TOR, signature_severity Audit, created_at 2008_12_01, updated_at 2019_10_17;)
alert tcp [104.218.63.73,104.218.63.74,104.218.63.75,104.218.63.76,104.244.72.115,104.244.72.221,104.244.72.251,104.244.72.33,104.244.72.99,104.244.73.126] any -> $HOME_NET any (msg:"ET TOR Known Tor Exit Node TCP Traffic group 2"; flags:S; reference:url,doc.emergingthreats.net/bin/view/Main/TorRules; threshold: type limit, track by_src, seconds 60, count 1; classtype:misc-attack; flowbits:set,ET.TorIP; sid:2520001; rev:3850; metadata:affected_product Any, attack_target Any, deployment Perimeter, tag TOR, signature_severity Audit, created_at 2008_12_01, updated_at 2019_10_17;)
    """  # noqa: E501

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], json=results)

        yield source


@patch.object(OSINTTrigger, "send_event")
def test_regex_source(send_event, symphony_storage, et_tor_source):
    trigger = OSINTTrigger(data_path=symphony_storage)
    trigger._run(et_tor_source)
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert len(bundle["objects"]) == 21  # 1 identity + 20 ipv4
    ipv4_results = set()

    for obj in bundle["objects"]:
        if obj["type"] == "ipv4-addr":
            ipv4_results.add(obj["value"])

    assert ipv4_results == {
        "103.15.28.215",
        "103.208.220.122",
        "103.208.220.226",
        "103.234.220.195",
        "103.249.28.195",
        "103.28.53.138",
        "103.68.109.167",
        "103.75.190.11",
        "104.200.20.46",
        "104.218.63.72",
        "104.218.63.73",
        "104.218.63.74",
        "104.218.63.75",
        "104.218.63.76",
        "104.244.72.115",
        "104.244.72.221",
        "104.244.72.251",
        "104.244.72.33",
        "104.244.72.99",
        "104.244.73.126",
    }


@pytest.fixture
def office365_ranges_source():
    source = {
        "name": "Office 365",
        "identity": "Office 365",
        "url": "https://endpoints.office.com/endpoints/worldwide?clientrequestid=b10c5ed1-bad1-445f-b386-b919946339a7",
        "frequency": 172800,
        "global_format": "json",
        "fields": ["*ipv4-addr", "*domain-name", "context:service"],
        "item_format": ["$.ips", "$.urls", "$.serviceAreaDisplayName"],
        "cache_results": False,
    }
    results = [
        {
            "id": 1,
            "serviceArea": "Exchange",
            "serviceAreaDisplayName": "Exchange Online",
            "urls": ["outlook.office.com", "outlook.office365.com"],
            "ips": [
                "13.107.6.152/31",
                "13.107.18.10/31",
                "2603:1006::/40",
                "2603:1016::/40",
            ],
            "tcpPorts": "80,443",
            "expressRoute": True,
            "category": "Optimize",
            "required": True,
        },
        {
            "id": 2,
            "serviceArea": "Exchange",
            "serviceAreaDisplayName": "Exchange Online",
            "urls": ["smtp.office365.com"],
            "ips": [
                "13.107.6.152/31",
                "13.107.128.0/22",
                "2603:1026:200::/39",
                "2603:1026:400::/39",
            ],
            "tcpPorts": "587",
            "expressRoute": True,
            "category": "Allow",
            "required": True,
        },
    ]

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], json=results)

        yield source


@patch.object(OSINTTrigger, "send_event")
def test_osint_office365(send_event, symphony_storage, office365_ranges_source):
    trigger = OSINTTrigger(data_path=symphony_storage)
    trigger._run(office365_ranges_source)
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    print(bundle)
    assert len(bundle["objects"]) == 7  # 1 identity + 3 ipv4 + 3 domain-name
    ipv4_results = set()

    for obj in bundle["objects"]:
        if obj["type"] == "ipv4-addr":
            ipv4_results.add(obj["value"])
            assert obj["x_inthreat_history"][0]["name"] == "Office 365"
            assert obj["x_inthreat_history"][0]["value"]["service"] == "Exchange Online"
            assert obj["x_inthreat_sources_refs"] == ["identity--58eca54e-775c-5b85-a40b-542d03be7426"]

    assert ipv4_results == {
        "13.107.6.152/31",
        "13.107.18.10/31",
        "13.107.128.0/22",
    }  # Only 3 different IP Addresses (one is shared)


@pytest.fixture
def sinkhole_source():
    source = {
        "name": "Sinkholes",
        "identity": "Sinkholes",
        "url": "https://raw.githubusercontent.com/brakmic/Sinkholes/master/Sinkholes_List.json",
        "frequency": 172800,
        "global_format": "json",
        "fields": ["ipv4-addr", "context:organization"],
        "item_format": ["$['IP Range']", "$.Organization"],  # Field with a space
        "cache_results": False,
    }
    results = [
        {
            "Organization": "Anubis",
            "IP Range": "195.22.26.192/26",
            "Whois": "anubisnetworks.com",
            "Notes": "https://www.proofpoint.com/us/daily-ruleset-update-summary-2015-08-14",
        },
        {
            "Organization": "Arbor Networks ASERT",
            "IP Range": "23.253.126.58",
            "Whois": "arbor-sinkhole.net",
            "Notes": "http://www.malwareurl.com/ns_listing.php?ns=ns1.arbor-sinkhole.net",
        },
    ]

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], json=results)

        yield source


@patch.object(OSINTTrigger, "send_event")
def test_sinkhole(send_event, symphony_storage, sinkhole_source):
    trigger = OSINTTrigger(data_path=symphony_storage)
    trigger._run(sinkhole_source)
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert len(bundle["objects"]) == 3  # 1 identity + 2 ipv4
    ipv4_results = set()

    for obj in bundle["objects"]:
        if obj["type"] == "ipv4-addr":
            ipv4_results.add(obj["value"])
            assert obj["x_inthreat_history"][0]["name"] == "Sinkholes"
            assert obj["x_inthreat_history"][0]["value"]["organization"] in [
                "Anubis",
                "Arbor Networks ASERT",
            ]
            assert "type" not in obj["x_inthreat_history"][0]["value"]

    assert ipv4_results == {"195.22.26.192/26", "23.253.126.58"}


@pytest.fixture
def csv_source():
    source = {
        "url": "https://urlhaus.abuse.ch/downloads/csv_recent/",
        "name": "URLhaus Tracker",
        "fields": [
            "_",
            "context:first_seen",
            "url",
            "context:status",
            "context:threat",
            "context:tags",
            "_",
            "_",
        ],
        "ignore": "#",
        "frequency": 300,
        "separator": ",",
        "global_format": "csv",
    }
    results = """################################################################
# abuse.ch URLhaus Database Dump (CSV - recent URLs only)      #
# Last updated: 2019-11-27 15:52:08 (UTC)                      #
#                                                              #
# Terms Of Use: https://urlhaus.abuse.ch/api/                  #
# For questions please contact urlhaus [at] abuse.ch           #
################################################################
#
# id,dateadded,url,url_status,threat,tags,urlhaus_link,reporter
"260692","2019-11-27","http://fs3n2.sendspace.com/dlpro/6fcd-ra.exe","online","malware_download","exe","","zbetcheckin"
"260691","2019-11-27","http://192.119.106.235/officeupd.tmp","online","malware_download","maze,runner","","anonymous"
"260690","2019-11-27","http://45.137.22.59/bbggmm/vbc.exe","online","malware_download","exe,windows","","zbetcheckin"
"260689","2019-11-27","http://45.137.22.59/bbggmm/win.exe","online","malware_download","exe","","zbetcheckin"
"""

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], text=results)
        yield source


@patch.object(OSINTTrigger, "send_event")
def test_csv(send_event, csv_source, symphony_storage):
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(csv_source)

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: URLhaus Tracker: 4 observables"

    observables = []
    for obj in bundle["objects"]:
        if obj["type"] == "url":
            assert obj["x_inthreat_history"][0]["value"]["tags"] in [
                "exe",
                "maze,runner",
                "exe,windows",
            ]
            observables.append(obj["value"])

    assert observables == [
        "http://fs3n2.sendspace.com/dlpro/6fcd-ra.exe",
        "http://192.119.106.235/officeupd.tmp",
        "http://45.137.22.59/bbggmm/vbc.exe",
        "http://45.137.22.59/bbggmm/win.exe",
    ]


@pytest.fixture
def csv_source_space():
    source = {
        "url": "https://bazaar.abuse.ch/downloads/csv_recent/",
        "name": "URLhaus Tracker",
        "fields": [
            "_",
            "context:first_seen",
            "url",
            "context:status",
            "context:threat",
            "context:tags",
            "_",
        ],
        "ignore": "#",
        "frequency": 300,
        "separator": ", ",
        "global_format": "csv",
    }
    results = """################################################################
# abuse.ch URLhaus Database Dump (CSV - recent URLs only)      #
# Last updated: 2019-11-27 15:52:08 (UTC)                      #
#                                                              #
# Terms Of Use: https://urlhaus.abuse.ch/api/                  #
# For questions please contact urlhaus [at] abuse.ch           #
################################################################
#
# id,dateadded,url,url_status,threat,tags,urlhaus_link,reporter
"260692", "2019-11-27", "http://fs3n2.sendspace.com/dlpro/6fcd-ra.exe", "online", "malware_download", "exe", ""
"260691", "2019-11-27", "http://192.119.106.235/officeupd.tmp", "online", "malware_download", "maze,runner", ""
"260690", "2019-11-27", "http://45.137.22.59/bbggmm/vbc.exe", "online", "malware_download", "exe,windows", ""
"260689", "2019-11-27", "http://45.137.22.59/bbggmm/win.exe", "online", "malware_download", "exe", ""
"""

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], text=results)
        yield source


@patch.object(OSINTTrigger, "send_event")
def test_csv_space(send_event, csv_source_space, symphony_storage):
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(csv_source_space)

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: URLhaus Tracker: 4 observables"

    observables = []
    for obj in bundle["objects"]:
        if obj["type"] == "url":
            assert obj["x_inthreat_history"][0]["value"]["tags"] in [
                "exe",
                "maze,runner",
                "exe,windows",
            ]
            observables.append(obj["value"])

    assert observables == [
        "http://fs3n2.sendspace.com/dlpro/6fcd-ra.exe",
        "http://192.119.106.235/officeupd.tmp",
        "http://45.137.22.59/bbggmm/vbc.exe",
        "http://45.137.22.59/bbggmm/win.exe",
    ]


@patch.object(OSINTTrigger, "send_event")
def test_csv_space_separator_single_char(send_event, csv_source_space, symphony_storage):
    # The previous test uses `, ` as a separator
    # The new fix makes it work with a single character separator
    csv_source_space["separator"] = ","
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(csv_source_space)

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: URLhaus Tracker: 4 observables"

    observables = []
    for obj in bundle["objects"]:
        if obj["type"] == "url":
            assert obj["x_inthreat_history"][0]["value"]["tags"] in [
                "exe",
                "maze,runner",
                "exe,windows",
            ]
            observables.append(obj["value"])

    assert observables == [
        "http://fs3n2.sendspace.com/dlpro/6fcd-ra.exe",
        "http://192.119.106.235/officeupd.tmp",
        "http://45.137.22.59/bbggmm/vbc.exe",
        "http://45.137.22.59/bbggmm/win.exe",
    ]


@pytest.fixture
def csv_ipv4_with_port_source():
    source = {
        "url": "https://urlhaus.abuse.ch/downloads/csv_recent/",
        "name": "URLhaus Tracker",
        "fields": [
            "_",
            "context:first_seen",
            "ipv4-addr",
            "context:status",
            "context:threat",
            "context:tags",
            "_",
            "_",
        ],
        "ignore": "#",
        "frequency": 300,
        "separator": ",",
        "global_format": "csv",
    }
    results = """################################################################
# abuse.ch URLhaus Database Dump (CSV - recent URLs only)      #
# Last updated: 2019-11-27 15:52:08 (UTC)                      #
#                                                              #
# Terms Of Use: https://urlhaus.abuse.ch/api/                  #
# For questions please contact urlhaus [at] abuse.ch           #
################################################################
#
# id,dateadded,url,url_status,threat,tags,urlhaus_link,reporter
"260691","2019-11-27","192.119.106.235:80","online","malware_download","maze,runner","","anonymous"
"260690","2019-11-27","45.137.22.59:443","online","malware_download","exe,windows","","zbetcheckin"
"260689","2019-11-27","33.25.22.60:445","online","malware_download","exe","","zbetcheckin"
"""

    with requests_mock.Mocker() as mock:
        mock.get(source["url"], text=results)
        yield source


@patch.object(OSINTTrigger, "send_event")
def test_csv_ipv4_port(send_event, csv_ipv4_with_port_source, symphony_storage):
    trigger = OSINTTrigger(data_path=symphony_storage)

    trigger._run(csv_ipv4_with_port_source)

    send_event.assert_called_once()
    name, bundle = get_name_and_bundle(symphony_storage, send_event)

    assert name == "OSINT: URLhaus Tracker: 3 observables"

    observables = []
    for obj in bundle["objects"]:
        if "value" in obj:
            observables.append(obj["value"])
            assert obj["x_inthreat_history"][0]["value"]["port"] in [80, 443, 445]

    assert observables == [
        "192.119.106.235",
        "45.137.22.59",
        "33.25.22.60",
    ]
