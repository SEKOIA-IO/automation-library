from collections import defaultdict

import pytest

from tests.data import expected_bundle, triage_raw_results
from triage_modules.action_triage_to_observables import TriageToObservablesAction


@pytest.fixture
def action():
    action = TriageToObservablesAction()
    return action


def test_run(action):
    arguments = {
        "triage_raw_results": [
            {
                "malware": "cobaltstrike",
                "samples": {
                    "210615-d716ysjlyx": {
                        "sample_c2s": [
                            "http://149.28.92.76:85/extension.css",
                            "149.28.92.76",
                            "cobalt.strikke:404",
                            "149.28.92.77:404",
                        ],
                        "sample_urls": ["http://149.28.92.76:86/delivery.ps1"],
                        "sample_hashes": [
                            "5e7fd9b0b65f8421dadf4b313a010735",
                            "3308b7b0d774c2e4a2638b6f77c527c51367b248",
                            "a0254738085cfc83f6aa936373d3318dcfd23c5ba57cf2704880f16a371c5cbc",
                            "45e2c6e90365dfb9955b58de990488f81559708780499418e2c3bf232430f52f"
                            "c4fc2696dadfe805dabeb0e28ea236a1264908792f8e100029bf8a9ccc9f7e40",
                        ],
                    }
                },
            }
        ]
    }
    res = action.run(arguments)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    numbers = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        numbers[item["type"]] += 1
        if item["type"] == "file":
            assert "SHA-512" in item["hashes"]
            assert "SHA-256" in item["hashes"]
            assert "SHA-1" in item["hashes"]
            assert "MD5" in item["hashes"]

    assert numbers["file"] == 1
    assert numbers["ipv4-addr"] == 2
    assert numbers["domain-name"] == 1
    assert numbers["url"] == 2

    assert res["observables"]["objects"][0]["x_external_references"][0]["url"] == "https://tria.ge/210615-d716ysjlyx"
    assert res["observables"]["objects"][2]["value"] == "cobalt.strikke"
    assert res["observables"]["objects"][2]["x_inthreat_tags"][0]["port"] == "404"


def test_get_observables_from_several_malware(action):
    arguments = {"triage_raw_results": triage_raw_results}
    res = action.run(arguments)
    bundle = res["observables"]

    for x in ["type", "value", "x_external_references"]:
        assert bundle["objects"][0][x] == expected_bundle["objects"][0][x]
        assert bundle["objects"][2][x] == expected_bundle["objects"][2][x]
    for x in ["type", "hashes", "x_external_references"]:
        assert bundle["objects"][1][x] == expected_bundle["objects"][1][x]
        assert bundle["objects"][3][x] == expected_bundle["objects"][3][x]


def test_get_observables_from_duplicated(action):
    arguments = {
        "triage_raw_results": [
            {
                "malware": "agenttesla",
                "samples": {
                    "212121-abcdefghij": {
                        "sample_c2s": [
                            "agent.tesla",
                            "149.28.92.76",
                            "149.28.92.76:443",
                        ],
                        "sample_urls": ["http://agent.tesla/payload.exe"],
                        "sample_hashes": [
                            "5e7fd9b0b65f8421dadf4b313a010735",
                            "3308b7b0d774c2e4a2638b6f77c527c51367b248",
                            "a0254738085cfc83f6aa936373d3318dcfd23c5ba57cf2704880f16a371c5cbc",
                            "45e2c6e90365dfb9955b58de990488f81559708780499418e2c3bf232430f52f"
                            "c4fc2696dadfe805dabeb0e28ea236a1264908792f8e100029bf8a9ccc9f7e40",
                        ],
                    },
                    "212121-abcdefghik": {
                        "sample_c2s": [
                            "agent.tesla",
                            "149.28.92.76",
                            "149.28.92.76:443",
                        ],
                        "sample_urls": ["http://agent.tesla/payload.exe"],
                        "sample_hashes": [
                            "5e7fd9b0b65f8421dadf4b313a010735",
                            "3308b7b0d774c2e4a2638b6f77c527c51367b248",
                            "a0254738085cfc83f6aa936373d3318dcfd23c5ba57cf2704880f16a371c5cbc",
                            "45e2c6e90365dfb9955b58de990488f81559708780499418e2c3bf232430f52f"
                            "c4fc2696dadfe805dabeb0e28ea236a1264908792f8e100029bf8a9ccc9f7e40",
                        ],
                    },
                },
            }
        ]
    }
    res = action.run(arguments)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    count = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        count[item["type"]] += 1
        if item["type"] == "file":
            assert "SHA-512" in item["hashes"]
            assert "SHA-256" in item["hashes"]
            assert "SHA-1" in item["hashes"]
            assert "MD5" in item["hashes"]

    assert count["ipv4-addr"] == 2  # One time with port and one time without
    assert count["domain-name"] == 1
    assert count["url"] == 1
    assert count["file"] == 1


def test_get_observables_from_invalid_pattern(action):
    arguments = {
        "triage_raw_results": [
            {
                "malware": "trickbot",
                "samples": {
                    "212121-abcdefghij": {
                        "sample_c2s": ["agent.tesla.com", "1.2.3.4.5", "ok:ok:ok"],
                        "sample_urls": ["http:://wrong.site/uri"],
                        "sample_hashes": [
                            "5e7fd9b0b65f8421dadf4b313a0107356",
                            "3308b7b0d774c2e4a2638b6f77c527c51367b248",
                        ],
                    },
                },
            }
        ]
    }
    res = action.run(arguments)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    count = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        count[item["type"]] += 1
        if item["type"] == "file":
            assert "SHA-1" in item["hashes"]
            assert "MD5" not in item["hashes"]

    print(res["observables"])
    assert count["ipv4-addr"] == 0
    assert count["domain-name"] == 1
    assert count["url"] == 0
    assert count["file"] == 1


def test_get_observables_from_ipv4_port(action):
    arguments = {
        "triage_raw_results": [
            {
                "malware": "revengerat",
                "samples": {
                    "210712-ewjd8nlgjs": {
                        "sample_c2s": ["37.0.11.45:5900"],
                        "sample_urls": [],
                        "sample_hashes": [
                            "bb8b7a3795e59ed655434320269bf3f3",
                            "b17f2307a90b4887ee9e99ad0b99905286d3c4da",
                            "2d91ae5d50302135a56f5062e516fbe8d0fdc609bf274074c81cf0e58366e880",
                            "01983acf0373c9bbbfc7bbe5342b34abc8c3a78b494508f84c02da6036ab380b"
                            "528b47cc0bc92729779f05743cc53a97b817d962154f3e435b764059ce9ca823",
                        ],
                    }
                },
            },
            {
                "malware": "totorat",
                "samples": {
                    "214365-a1z2e3r4t5": {
                        "sample_c2s": ["37.0.11.45"],
                        "sample_urls": [],
                        "sample_hashes": [
                            "ab8b7a3795e59ed655434320269bf3f3",
                            "a17f2307a90b4887ee9e99ad0b99905286d3c4da",
                            "1d91ae5d50302135a56f5062e516fbe8d0fdc609bf274074c81cf0e58366e880",
                            "91983acf0373c9bbbfc7bbe5342b34abc8c3a78b494508f84c02da6036ab380b"
                            "528b47cc0bc92729779f05743cc53a97b817d962154f3e435b764059ce9ca823",
                        ],
                    }
                },
            },
        ]
    }
    res = action.run(arguments)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    count = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        count[item["type"]] += 1
        if item["type"] == "file":
            assert "SHA-512" in item["hashes"]
            assert "SHA-256" in item["hashes"]
            assert "SHA-1" in item["hashes"]
            assert "MD5" in item["hashes"]

    assert count["ipv4-addr"] == 2
    assert count["domain-name"] == 0
    assert count["url"] == 0
    assert count["file"] == 2

    print(res["observables"]["objects"])
    print(res["observables"]["objects"][1])
    assert res["observables"]["objects"][0]["value"] == "37.0.11.45"
    assert res["observables"]["objects"][0]["x_inthreat_tags"][0]["port"] == "5900"
    assert res["observables"]["objects"][2]["value"] == "37.0.11.45"
    assert "port" not in res["observables"]["objects"][2]["x_inthreat_tags"][0]


def test_get_observables_from_ipv4_single_ip(action):
    """ "
    Make sure the IP is not duplicated
    """
    arguments = {
        "triage_raw_results": [
            {
                "malware": "revengerat",
                "samples": {
                    "210712-ewjd8nlgjs": {
                        "sample_c2s": ["37.0.11.45:5900"],
                        "sample_urls": [],
                        "sample_hashes": [
                            "bb8b7a3795e59ed655434320269bf3f3",
                            "b17f2307a90b4887ee9e99ad0b99905286d3c4da",
                            "2d91ae5d50302135a56f5062e516fbe8d0fdc609bf274074c81cf0e58366e880",
                            "01983acf0373c9bbbfc7bbe5342b34abc8c3a78b494508f84c02da6036ab380b"
                            "528b47cc0bc92729779f05743cc53a97b817d962154f3e435b764059ce9ca823",
                        ],
                    }
                },
            },
            {
                "malware": "totorat",
                "samples": {
                    "214365-a1z2e3r4t5": {
                        "sample_c2s": ["37.0.11.45:5900"],
                        "sample_urls": [],
                        "sample_hashes": [
                            "bb8b7a3795e59ed655434320269bf3f3",
                            "b17f2307a90b4887ee9e99ad0b99905286d3c4da",
                            "2d91ae5d50302135a56f5062e516fbe8d0fdc609bf274074c81cf0e58366e880",
                            "01983acf0373c9bbbfc7bbe5342b34abc8c3a78b494508f84c02da6036ab380b"
                            "528b47cc0bc92729779f05743cc53a97b817d962154f3e435b764059ce9ca823",
                        ],
                    }
                },
            },
            {
                "malware": "totorat",
                "samples": {
                    "214365-a1z2e3r4t5": {
                        "sample_c2s": ["37.0.11.45"],
                        "sample_urls": [],
                        "sample_hashes": [],
                    }
                },
            },
        ]
    }
    res = action.run(arguments)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    count = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        count[item["type"]] += 1

    assert count["ipv4-addr"] == 2
    assert count["file"] == 1


def test_get_observables_from_url_without_http(action):
    """ "
    Make sure the IP is not duplicated
    """
    arguments = {
        "triage_raw_results": [
            {
                "malware": "amadey",
                "samples": {
                    "230220-tbqs7sah7x": {
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
                },
            },
        ]
    }
    res = action.run(arguments)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    count = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        count[item["type"]] += 1

    assert count["url"] == 1
    for item in res["observables"]["objects"]:
        if item["type"] == "url":
            assert item["value"] == "http://193.233.20.15/dF30Hn4m/index.php"
    assert count["file"] == 1


def test_exclude_wrong_domain_port_pattern(action):
    """ "
    Make sure the domain:port pattern includes only one port
    """
    arguments = {
        "triage_raw_results": [
            {
                "malware": "xworm",
                "samples": {
                    "250205-ep1g8synhz": {
                        "sample_c2s": ["dvd-crossword.gl.at.ply.gg:43216:43216", "dvd-crossword.gl.at.ply.gg:43216"],
                        "sample_urls": [],
                        "sample_hashes": [
                            "0de45ff4c9d8c08551619009eb07265a",
                            "b16530d8c5d9358e63ec1113e3e22aa80c51102f",
                            "c68385c8744b3558b7357eccaca2ad45f3089578454fe2fd31e17aff3ff456c3",
                            "70716ae8d4c0b2d77ab4685b017aa2ed92c56206f8d5cc42793cc83ffed0f2ba"
                            "d34fc8220ed82d4e0eee641c6b71820b6f4c4f82beba00591b4af6927bf67649",
                        ],
                    }
                },
            },
        ]
    }
    res = action.run(arguments)
    print(res)
    assert "observables" in res
    assert res["observables"]["type"] == "bundle"

    count = defaultdict(lambda: 0)
    for item in res["observables"]["objects"]:
        count[item["type"]] += 1

    assert count["file"] == 1
    assert count["domain-name"] == 1

    for item in res["observables"]["objects"]:
        if item["type"] == "domain-name":
            assert item["value"] == "dvd-crossword.gl.at.ply.gg"
            assert item["x_inthreat_tags"][0]["port"] == "43216"
    assert count["file"] == 1
