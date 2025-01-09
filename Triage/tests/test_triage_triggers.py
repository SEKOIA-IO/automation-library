import json
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests_mock

from tests.data import (
    query_210609_8ddyb8de5s,
    query_210609_c67qy7hmpe,
    query_210609_c67qy7hmpe_static,
    query_210614_dgzch44pyn,
    query_211006_qkva7sbdgj,
    query_211118_a13draede7,
    query_211202_qfystsbha9,
    query_211220_hdgsjaafbq,
    query_211228_jjytnscbdn,
    query_230220_tbqs7sah7x,
    query_icedid,
    query_kdfjzkhfehvfjz,
    query_qakbot,
    query_240828_btyyeszang,
    query_240828_btyyeszang_static,
    query_240908_tpps3axgmd_static,
    query_241118_wj1z9asdqn,
    query_241113_rawlystckq,
    query_250106_fypb1azkcr,
)
from triage_modules.trigger_triage import TriageConfigsTrigger

sample_id_regex = "[0-9]{6}-[0-9a-z]{10}"


@pytest.fixture
def trigger(symphony_storage):
    trigger = TriageConfigsTrigger()
    trigger.module.configuration = {
        "api_key": "toto",
        "api_url": "https://api.tria.ge/",
    }
    trigger.configuration = {
        "frequency": 604800,
        "malware_list": ["icedid", "qakbot", "kdfjzkhfehvfjz"],
        "exclude_signed": False,
    }
    trigger.send_event = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def trigger2(symphony_storage):
    trigger = TriageConfigsTrigger()
    trigger.module.configuration = {
        "api_key": "toto",
        "api_url": "https://api.tria.ge/",
    }
    trigger.configuration = {
        "frequency": 604800,
        "malware_list": [],
        "exclude_signed": True,
    }
    trigger.send_event = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def trigger3(symphony_storage):
    trigger = TriageConfigsTrigger()
    trigger.module.configuration = {
        "api_key": "toto",
        "api_url": "https://api.tria.ge/",
    }
    trigger.configuration = {
        "frequency": 604800,
        "malware_list": [],
        "exclude_signed": True,
        "exclude_suspicious_analysis": True,
    }
    trigger.send_event = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def triage_mock():
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.tria.ge/v0/search?query=family:icedid&limit=200",
            json=query_icedid,
        )
        m.get(
            "https://api.tria.ge/v1/samples/210609-c67qy7hmpe/overview.json",
            json=query_210609_c67qy7hmpe,
        )
        m.get(
            "https://api.tria.ge/v1/samples/210609-8ddyb8de5s/overview.json",
            json=query_210609_8ddyb8de5s,
        )
        m.get(
            "https://api.tria.ge/v0/search?query=family:qakbot&limit=200",
            json=query_qakbot,
        )
        m.get(
            "https://api.tria.ge/v0/search?query=family:kdfjzkhfehvfjz&limit=200",
            json=query_kdfjzkhfehvfjz,
        )
        m.get(
            "https://api.tria.ge/v1/samples/210614-dgzch44pyn/overview.json",
            json=query_210614_dgzch44pyn,
        )
        m.get(
            "https://api.tria.ge/v1/samples/211006-qkva7sbdgj/overview.json",
            json=query_211006_qkva7sbdgj,
        )
        m.get(
            "https://api.tria.ge/v1/samples/211118-a13draede7/overview.json",
            json=query_211118_a13draede7,
        )
        m.get(
            "https://api.tria.ge/v1/samples/211202-qfystsbha9/overview.json",
            json=query_211202_qfystsbha9,
        )
        m.get(
            "https://api.tria.ge/v1/samples/211220-hdgsjaafbq/overview.json",
            json=query_211220_hdgsjaafbq,
        )
        m.get(
            "https://api.tria.ge/v1/samples/211228-jjytnscbdn/overview.json",
            json=query_211228_jjytnscbdn,
        )
        m.get(
            "https://api.tria.ge/v1/samples/230220-tbqs7sah7x/overview.json",
            json=query_230220_tbqs7sah7x,
        )
        m.get(
            "https://api.tria.ge/v0/samples/210609-c67qy7hmpe/reports/static",
            json=query_210609_c67qy7hmpe_static,
        )
        m.get(
            "https://api.tria.ge/v0/samples/240828-btyyeszang/overview.json",
            json=query_240828_btyyeszang,
        )
        m.get(
            "https://api.tria.ge/v0/samples/240828-btyyeszang/reports/static",
            json=query_240828_btyyeszang_static,
        )
        m.get(
            "https://api.tria.ge/v0/samples/240908-tpps3axgmd/reports/static",
            json=query_240908_tpps3axgmd_static,
        )
        m.get(
            "https://api.tria.ge/v0/samples/241118-wj1z9asdqn/overview.json",
            json=query_241118_wj1z9asdqn,
        )
        m.get(
            "https://api.tria.ge/v0/samples/241113_rawlystckq/overview.json",
            json=query_241113_rawlystckq,
        )
        m.get(
            "https://api.tria.ge/v0/samples/250106-fypb1azkcr/overview.json",
            json=query_250106_fypb1azkcr,
        )
        yield m


def test_run(trigger, triage_mock, symphony_storage):
    trigger._run()

    trigger.send_event.assert_called()
    assert trigger.send_event.call_count == 1

    # Read results from disk
    kwargs = trigger.send_event.call_args.kwargs
    file_path = Path(symphony_storage).joinpath(kwargs["directory"]).joinpath(kwargs["event"]["file_path"])
    triage_raw_results = json.loads(file_path.read_text())

    expected_raw_results = [
        {
            "malware": "icedid",
            "samples": {
                "sample_id1": {
                    "sample_c2s": ["str"],
                    "sample_urls": ["str"],
                    "sample_hashes": ["str"],
                }
            },
        },
        {
            "malware": "qakbot",
            "samples": {
                "sample_id1": {
                    "sample_c2s": ["str"],
                    "sample_urls": ["str"],
                    "sample_hashes": ["str"],
                }
            },
        },
    ]
    assert triage_raw_results[0]["malware"] == expected_raw_results[0]["malware"]
    assert triage_raw_results[1]["malware"] == expected_raw_results[1]["malware"]

    triage_sample = list(triage_raw_results[0]["samples"].keys())[0]
    triage_sample_iocs_keys = list(triage_raw_results[0]["samples"][triage_sample].keys())
    expected_sample_iocs_keys = list(expected_raw_results[0]["samples"]["sample_id1"].keys())
    assert triage_sample_iocs_keys == expected_sample_iocs_keys
    # ASSERT THAT NO RESULT EXISTS FOR THE MALWARE kdfjzkhfehvfjz (doesn't
    # exist)
    assert len(triage_raw_results) == 2


def test_get_malware_samples(trigger, triage_mock):
    # ASSERT THAT SAMPLES_ID IS A LIST OF SAMPLE_ID
    samples_id = trigger.get_malware_samples("icedid", 604800)
    for sample_id in samples_id:
        assert re.match(sample_id_regex, sample_id)


def test_get_sample_iocs(trigger, triage_mock):
    # ASSERT THAT SAMPLE_IOCS OF A SPECIFIC ANALYSIS CORRESPONDS
    sample_iocs = trigger.get_sample_iocs("icedid", "210609-c67qy7hmpe")
    assert sample_iocs == {
        "sample_c2s": ["dilmopozira.top"],
        "sample_urls": [],
        "sample_hashes": [
            "a99f6f41e94c0c9dac365e9bd194391c",
            "12c8adf784f2e3072cd6142d87c052e3fddde059",
            "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
            "569184b18e66eaa908744acfddc83ec954d1e62d69c254634c60e48f8f5b036b"
            "94ab8ddb32a8431c4a17312a97b4cc4a53dfef3957bf5dc627449ed8e88427df",
        ],
    }


def test_get_sample_unsigned_iocs_exclude_signed_on(trigger2, triage_mock):
    # ASSERT THAT SAMPLE_IOCS OF A SPECIFIC ANALYSIS WITHOUT SIGNATURE CORRESPONDS WHEN EXCLUDE SIGNED IS ON
    sample_iocs = trigger2.get_sample_iocs("icedid", "210609-c67qy7hmpe")
    assert sample_iocs == {
        "sample_c2s": ["dilmopozira.top"],
        "sample_urls": [],
        "sample_hashes": [
            "a99f6f41e94c0c9dac365e9bd194391c",
            "12c8adf784f2e3072cd6142d87c052e3fddde059",
            "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
            "569184b18e66eaa908744acfddc83ec954d1e62d69c254634c60e48f8f5b036b"
            "94ab8ddb32a8431c4a17312a97b4cc4a53dfef3957bf5dc627449ed8e88427df",
        ],
    }


def test_get_sample_signed_iocs_exclude_signed_on(trigger2, triage_mock):
    # ASSERT THAT SAMPLE_IOCS OF A SPECIFIC ANALYSIS WITH a SIGNED BINARY CORRESPONDS WHEN EXCLUDE SIGNED IS ON
    sample_iocs = trigger2.get_sample_iocs("icedid", "240828_btyyeszang")
    assert sample_iocs == {
        "sample_c2s": [],
        "sample_urls": [],
        "sample_hashes": [],
    }


def test_check_sample_without_signature(trigger2, triage_mock):
    # ASSERT THAT SIGNATURE OF A SPECIFIC ANALYSIS IS NOT PRESENT
    sample_signature = trigger2.check_sample_signature("210609-c67qy7hmpe")
    assert sample_signature is False


def test_check_sample_with_signature(trigger2, triage_mock):
    # ASSERT THAT SIGNATURE OF A SPECIFIC ANALYSIS IS NOT PRESENT
    sample_signature = trigger2.check_sample_signature("240828-btyyeszang")
    assert sample_signature is True


def test_check_report_with_multiple_signatures(trigger2, triage_mock):
    # ASSERT THAT SIGNATURE OF A SPECIFIC ANALYSIS IS NOT PRESENT
    sample_signature = trigger2.check_sample_signature("240908-tpps3axgmd")
    assert sample_signature is True


def test_check_report_without_enough_dynamic_analysis(trigger3, triage_mock):
    # ASSERT THAT CHECK SUSPICIOUS IS TRUE WHEN DYNAMIC ANALYSIS IS LESS THAN 2
    analysis_is_suspicious = trigger3.check_suspicious_analysis("241118-wj1z9asdqn", query_241118_wj1z9asdqn)
    assert analysis_is_suspicious is True


def test_check_report_with_enough_dynamic_analysis(trigger3, triage_mock):
    # ASSERT THAT CHECK SUSPICIOUS IS FALSE WHEN DYNAMIC ANALYSIS IS MORE OR EQUAL TO 2
    analysis_is_suspicious = trigger3.check_suspicious_analysis("210609-c67qy7hmpe", query_210609_c67qy7hmpe)
    assert analysis_is_suspicious is False


def test_check_report_with_suspicious_score_gap(trigger3, triage_mock):
    # ASSERT THAT CHECK SUSPICIOUS IS TRUE WHEN DYNAMIC ANALYSIS HAS A SCORE GAP
    analysis_is_suspicious = trigger3.check_suspicious_analysis("241113_rawlystckq", query_241113_rawlystckq)
    assert analysis_is_suspicious is True


def test_check_report_without_suspicious_score_gap(trigger3, triage_mock):
    # ASSERT THAT CHECK SUSPICIOUS IS FALSE WHEN DYNAMIC ANALYSIS DOES NOT HAVE A SCORE GAP
    analysis_is_suspicious = trigger3.check_suspicious_analysis("210609-c67qy7hmpe", query_210609_c67qy7hmpe)
    assert analysis_is_suspicious is False


def test_check_report_without_suspicious_linux(trigger3, triage_mock):
    # ASSERT THAT CHECK SUSPICIOUS IS FALSE WHEN DYNAMIC ANALYSIS IS ON LINUX
    analysis_is_suspicious = trigger3.check_suspicious_analysis("250106-fypb1azkcr", query_250106_fypb1azkcr)
    assert analysis_is_suspicious is False


def test_get_malware_iocs(trigger, triage_mock):
    # ASSERT THAT MALWARE_IOCS OF SEVERAL MALWARE ANALYSIS CORRESPONDS
    malware_iocs = trigger.get_malware_iocs("icedid", ["210609-c67qy7hmpe", "210609-8ddyb8de5s"])
    assert malware_iocs["malware"] == "icedid"
    assert malware_iocs["samples"]["210609-c67qy7hmpe"]["sample_c2s"] == ["dilmopozira.top"]
    assert malware_iocs["samples"]["210609-8ddyb8de5s"]["sample_c2s"] == ["potimomainger.top"]
    assert malware_iocs["samples"]["210609-c67qy7hmpe"]["sample_urls"] == []
    assert malware_iocs["samples"]["210609-8ddyb8de5s"]["sample_urls"] == []
    assert malware_iocs["samples"]["210609-c67qy7hmpe"]["sample_hashes"] == [
        "a99f6f41e94c0c9dac365e9bd194391c",
        "12c8adf784f2e3072cd6142d87c052e3fddde059",
        "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
        "569184b18e66eaa908744acfddc83ec954d1e62d69c254634c60e48f8f5b036b"
        "94ab8ddb32a8431c4a17312a97b4cc4a53dfef3957bf5dc627449ed8e88427df",
    ]
    assert malware_iocs["samples"]["210609-8ddyb8de5s"]["sample_hashes"] == [
        "4ca603fb87d28b9da39f1174a426da43",
        "d265a8d6da40244503867c8d59d8eeb136544a3d",
        "d7b9ef581459a0d8f94b789ae07a9e0892c0f0d0bcc7416a45471fe817ce377d",
        "53907a5812f70114e44edab589e9455eddcd3fd0e997475dada178ea568c943c"
        "8db0d41cb58b725832973ed035fb47f6fc412c210ee8760767ab0047becbf38d",
    ]


def test_get_malware_c2s(trigger, triage_mock):
    # ASSERT THAT MALWARE_IOCS OF AN ANALYSIS WITH SEVERAL URL AS IN url4cnc
    # CORRESPONDS
    sample_iocs = trigger.get_sample_iocs("raccoon", "211006-qkva7sbdgj")
    assert sample_iocs == {
        "sample_c2s": [
            "http://teletop.top/iot3redisium",
            "http://teleta.top/iot3redisium",
            "https://t.me/iot3redisium",
        ],
        "sample_urls": [],
        "sample_hashes": [
            "f626600409cd7eaa72c1105a52002cd5",
            "f6f5202b9e38a257f5f0bbc784eb4b9ff6c481af",
            "459d4fd9bd7ec69f47d9c3306856a7e6ec39b17ff2c88ae80dcac8e9daba760e",
            "f0f6c423af7b0746c6687048b49d378988714321d5d353400616929dfc591da8"
            "77fe658d9c6a36dbb859c33b788f8005db72fa981944a80476d57929d7a46524",
        ],
    }


def test_get_malware_hashes(trigger, triage_mock):
    # ASSERT THAT HASHES CORRESPOND TO THOSE OF THE MALWARE SAMPLE AND NOT AN EXTRACTED FILE
    sample_iocs = trigger.get_sample_iocs("asyncrat", "211118-a13draede7")
    assert sample_iocs == {
        "sample_c2s": [
            "144.217.68.78:3010",
        ],
        "sample_urls": [],
        "sample_hashes": [
            "44da69bb3848a28c8ba2238537a90da6",
            "d538186f09636dc7ce559452bb9b7632fe99fb5c",
            "d90936e1911b9a666b60051a817ae1b91f26e8b89e4d5041bdcad77ea2087c66",
            "7d834ab7a9783485b130835215eb2c0766d104a3713a8787971572eac5d21721"
            "0144a008b6aa38df4e6785e4739086fae8c78efc79394d2f527f2a964a51b326",
        ],
    }


def test_get_malware_null_url(trigger, triage_mock):
    # ASSERT THAT NO ERROR OCCURS WHEN URL VALUE IS NULL
    sample_iocs = trigger.get_sample_iocs("cobaltstrike", "211202-qfystsbha9")
    assert sample_iocs == {
        "sample_c2s": [
            "http://6a2c-91-132-175-60.ngrok.io:80/ga.js",
        ],
        "sample_urls": [],
        "sample_hashes": [
            "513cf6eccb0d244d49d75cfc3c0e8bc8",
            "947c26ca2c3ace7a8a1e013469d18c00f81ddc78",
            "a08c334b4787086ae997c05f7077e4c6955fd5cc8a141e58d1534fe0683fc44f",
            "274e086db431aea4fe41c94a59e56b4f62126113543afd7237cfe9793df3ba4b"
            "ee393055df7a7b2e2dd18c0232eab58956a3a6a1adf5c3f4f5cfb968ae77f92b",
        ],
    }


def test_get_malware_invalid_c2(trigger, triage_mock):
    # ASSERT THAT NO ERROR OCCURS WHEN C2 IS INVALID (BASE64 ENCODED)
    sample_iocs = trigger.get_sample_iocs("njrat", "211220-hdgsjaafbq")
    assert sample_iocs == {
        "sample_c2s": [],
        "sample_urls": [],
        "sample_hashes": [
            "ab71d3024ba35c9025ead27b28c075bd",
            "67a1c777aa8dc845de80ac5da0c26088bccbf838",
            "707fef4235cf1842dd9090a412f0b986d5901e5a7728c89804eebdaad40c2468",
            "cf3f96595170102d21b597d2cbb692844c960ec3ed8acdc3b37e5421cd4dc26c"
            "ab2c3e903773f2ffa03c443fec06f3d18520d4b2fd0fa3d8c8eb7ef2fe9febaf",
        ],
    }


def test_get_malware_invalid_url(trigger, triage_mock):
    # ASSERT THAT NO ERROR OCCURS WHEN URL IS INVALID (ARRAY IN ARRAY)
    sample_iocs = trigger.get_sample_iocs("agenttesla", "211228-jjytnscbdn")
    assert sample_iocs == {
        "sample_c2s": ["http://microsoftiswear.duckdns.org/y/inc/c3809dbf90d26b.php"],
        "sample_urls": ["https://bitly.com/ghgfsfdsfdsfadasdqw"],
        "sample_hashes": [
            "0b2df4c0540407d1e553ec10b3bc6c9a",
            "e85e924e58e0d305f8f4846ce332b1edb252fef8",
            "aede7d382658c9bd7b6244ca502b020fc8301a05d253b63897a37aaabab6328a",
            "ff54640c41840efb4816ebbfe901d1449fa257158f047da723052789559a0c20"
            "9516b915cce78066f3c4ed17d833af232063d2e542914a4e3500fdd03132c752",
        ],
    }


def test_get_malware_url_without_scheme(trigger, triage_mock):
    # ASSERT THAT NO ERROR OCCURS WHEN URL IS INVALID (ARRAY IN ARRAY)
    sample_iocs = trigger.get_sample_iocs("amadey", "230220-tbqs7sah7x")
    assert sample_iocs == {
        "sample_c2s": ["193.233.20.15/dF30Hn4m/index.php"],
        "sample_urls": [],
        "sample_hashes": [
            "0975c6819cc2c657b6fb6fcc0cc3fea0",
            "5361dbd526a501fc7a7acfdba5b1c4f11e2fddaf",
            "9a8dc6c456f0f9e82099d5e392c6e6b2b4818356bbcb63d247d23be9057dea46",
            "6fbeefdee3f0158bb32c162ef4bd6622d28d9745061238211fb90fca1e9a75b3"
            "548233b00c607ab180084fabc9989bee74d6b45c6c9ada5a79e23bff6f0c31cd",
        ],
    }


def test_run_error(trigger):
    with requests_mock.Mocker() as m:
        m.register_uri("GET", "/v0/search", status_code=500)
        trigger._run()
        assert trigger.log.called is True


def test_run_wrong_json(trigger):
    with requests_mock.Mocker() as m:
        m.register_uri("GET", "/v0/search", text="wrong]")
        trigger._run()
        assert trigger.log.called is True


def test_get_sample_iocs_error_not_found(trigger):
    with requests_mock.Mocker() as m:
        m.get("https://api.tria.ge/v1/samples/bar/overview.json", status_code=404)
        trigger.get_sample_iocs("foo", "bar")
        assert trigger.log.called is True


def test_get_sample_iocs_wrong_json(trigger):
    with requests_mock.Mocker() as m:
        m.get("https://api.tria.ge/v1/samples/bar/overview.json", text="bad]")
        trigger.get_sample_iocs("foo", "bar")
        assert trigger.log.called is True
