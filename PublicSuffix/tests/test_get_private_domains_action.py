# natives
import json
import os
from shutil import rmtree
from tempfile import mkdtemp

# third parties
import pytest
import requests_mock
from sekoia_automation import constants

# internals
from public_suffix.get_private_domains_action import GetPrivateDomainsAction

FILE = """
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this

// ===BEGIN ICANN DOMAINS===

// ac : https://en.wikipedia.org/wiki/.ac
ac
com.ac
edu.ac

// ad : https://en.wikipedia.org/wiki/.ad
ad
nom.ad

// ae : https://en.wikipedia.org/wiki/.ae
// see also: "Domain Name Eligibility Policy" at http://www.aeda.ae/eng/aepolicy.php
ae
co.ae

// ===END ICANN DOMAINS===
// ===BEGIN PRIVATE DOMAINS===
// (Note: these are in alphabetical order by company name)

// 1GB LLC : https://www.1gb.ua/
// Submitted by 1GB LLC <noc@1gb.com.ua>
cc.ua
inf.ua
ltd.ua

// Adobe : https://www.adobe.com/
// Submitted by Ian Boston <boston@adobe.com>
adobeaemcloud.com
adobeaemcloud.net
*.dev.adobeaemcloud.com

// ===END PRIVATE DOMAINS===
"""


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def file_mock():
    with requests_mock.Mocker() as mock:
        mock.get(GetPrivateDomainsAction.url, text=FILE)
        yield mock


def test_download_file(symphony_storage, file_mock):
    action = GetPrivateDomainsAction()
    result = action.run({})

    assert "domains_path" in result
    path = os.path.join(symphony_storage, result["domains_path"])
    assert os.path.exists(path) is True
    with open(path) as fp:
        domains = json.load(fp)
    assert isinstance(domains, list)
    assert len(domains) == 6

    assert "*.dev.adobeaemcloud.com" not in domains  # *. not in domains
    assert "dev.adobeaemcloud.com" in domains

    assert "ac" not in domains  # ICANN
    assert "edu.ac" not in domains  # ICANN

    assert "ltd.ua" in domains
