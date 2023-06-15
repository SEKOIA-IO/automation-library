import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_ctl import OnypheCtlAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheCtlAction


@pytest.fixture
def ressource():
    return "ctl/google.com"


@pytest.fixture
def bad_ressource():
    return "ctl/examplecom"


@pytest.fixture
def arguments():
    return {"domain": "gOOgle.com"}


@pytest.fixture
def bad_arguments():
    return [
        (InvalidArgument, {"domain": 33}),
        (InvalidArgument, {"domain": "examplecom"}),
        (TypeError, {}),
    ]


ctl_result = {
    "count": 5,
    "error": 0,
    "max_page": 1,
    "myip": "185.122.161.248",
    "page": 1,
    "results": [
        {
            "@category": "ctl",
            "@timestamp": "2019-09-16T17:31:56.000Z",
            "@type": "doc",
            "seen_date": "2019-09-16",
            "source": "Google Rocketeer",
            "domain": ["googleapis.com", "youtube.com", "google.com"],
            "hostname": [
                "clients.google.com",
                "docs.google.com",
                "drive.google.com",
                "gdata.youtube.com",
                "googleapis.com",
                "photos.google.com",
                "upload.google.com",
                "upload.video.google.com",
                "upload.youtube.com",
                "uploads.stage.gdata.youtube.com",
            ],
            "ip": [
                "216.58.198.207",
                "216.58.206.238",
                "2a00:1450:4007:80a:0:0:0:200f",
                "216.58.209.238",
                "172.217.17.132",
                "2a00:1450:4007:809:0:0:0:200e",
                "2a00:1450:400e:80d:0:0:0:2004",
                "216.58.209.239",
                "2a00:1450:4007:80f:0:0:0:200e",
                "216.58.204.111",
                "2a00:1450:400e:80d:0:0:0:200e",
                "2a00:1450:4007:80f:0:0:0:200f",
                "216.58.215.46",
                "2a00:1450:4007:808:0:0:0:200e",
                "216.58.198.206",
                "2a00:1450:4007:809:0:0:0:200f",
            ],
            "organization": "Google LLC",
            "host": ["gdata", "photos", "drive", "upload", "docs"],
            "tld": "com",
            "country": "US",
            "basicconstraints": ["critical"],
            "ca": "false",
            "extkeyusage": ["serverAuth"],
            "fingerprint": {
                "md5": "dc750d12d60f540b735f6dc02c033b3b",
                "sha1": "44f255b63fea9a10a2f9c0e3d70d55d0890bf305",
                "sha256": "d760ba8eebb453144eca482cde35b85d3f129d6469d99d348d720f8272f49c3f",
            },
            "issuer": {
                "commonname": "GTS CA 1O1",
                "country": "US",
                "organization": "Google Trust Services",
            },
            "keyusage": ["critical", "digitalSignature", "keyEncipherment"],
            "publickey": {
                "algorithm": "rsaEncryption",
                "exponent": "65537",
                "length": "2048",
            },
            "serial": "a6:08:9d:d9:34:4f:6c:3d:08:00:00:00:00:13:16:ce",
            "signature": {"algorithm": "sha256WithRSAEncryption"},
            "subdomains": "video.google.com",
            "subject": {
                "altname": [
                    "upload.youtube.com",
                    "*.upload.youtube.com",
                    "*.googleapis.com",
                    "*.drive.google.com",
                    "uploads.stage.gdata.youtube.com",
                    "upload.video.google.com",
                    "*.gdata.youtube.com",
                    "*.upload.google.com",
                    "upload.google.com",
                    "*.docs.google.com",
                    "*.clients.google.com",
                    "*.photos.google.com",
                    "*.youtube-3rd-party.com",
                ],
                "commonname": "upload.video.google.com",
            },
            "validity": {
                "notafter": "2019-11-28T20:15:53.000Z",
                "notbefore": "2019-09-05T20:15:53.000Z",
            },
            "version": "v3",
            "wildcard": "true",
        },
        {
            "@category": "ctl",
            "@timestamp": "2019-09-16T00:21:39.000Z",
            "@type": "doc",
            "country": "US",
            "domain": ["8888.google", "dns.google", "google.com"],
            "hostname": [
                "8888.google",
                "dns.google",
                "dns.google.com",
                "dns64.dns.google",
            ],
            "ip": [
                "8.8.8.8",
                "2001:4860:4860:0:0:0:0:64",
                "2001:4860:4860:0:0:0:0:6464",
                "8.8.4.4",
                "2001:4860:4860:0:0:0:0:8844",
                "2001:4860:4860:0:0:0:0:8888",
            ],
            "organization": "Google LLC",
            "seen_date": "2019-09-16",
            "source": "Google Argon 2019",
            "tld": ["com", "google"],
            "basicconstraints": ["critical"],
            "ca": "false",
            "extkeyusage": ["serverAuth"],
            "fingerprint": {
                "md5": "b51f3521597eaa26ef9a426321acdfd8",
                "sha1": "6a3e6e340cc1f5514daa8068b5641196e00ae704",
                "sha256": "e529ff01c70f58a180d196f9b36722b0ecfd246c0d8cb5774882f0efee0cc185",
            },
            "host": ["dns", "dns64"],
            "issuer": {
                "commonname": "GTS CA 1O1",
                "country": "US",
                "organization": "Google Trust Services",
            },
            "keyusage": ["critical", "digitalSignature", "keyEncipherment"],
            "publickey": {
                "algorithm": "rsaEncryption",
                "exponent": "65537",
                "length": "2048",
            },
            "serial": "db:8d:33:6e:e8:7d:04:82:02:00:00:00:00:42:ff:99",
            "signature": {"algorithm": "sha256WithRSAEncryption"},
            "subject": {
                "altname": [
                    "*.dns.google.com",
                    "dns.google.com",
                    "8888.google",
                    "dns64.dns.google",
                    "dns.google",
                ],
                "commonname": "dns.google",
            },
            "validity": {
                "notafter": "2019-11-28T20:18:38.000Z",
                "notbefore": "2019-09-05T20:18:38.000Z",
            },
            "version": "v3",
            "wildcard": "true",
        },
        {
            "@category": "ctl",
            "@timestamp": "2019-09-15T15:42:41.000Z",
            "@type": "doc",
            "country": "US",
            "domain": "google.com",
            "hostname": ["inbox.google.com", "mail.google.com"],
            "ip": [
                "172.217.17.37",
                "2a00:1450:400e:809:0:0:0:2005",
                "216.58.213.165",
                "2a00:1450:4007:811:0:0:0:2005",
            ],
            "organization": "Google LLC",
            "seen_date": "2019-09-15",
            "source": "Google Rocketeer",
            "host": ["inbox", "mail"],
            "tld": "com",
            "basicconstraints": ["critical"],
            "ca": "false",
            "extkeyusage": ["serverAuth"],
            "fingerprint": {
                "md5": "85d88fbe3fdae3749dd793a9e4cb7a3f",
                "sha1": "ec4b11bf43effeabf125a35c70f401287738fb83",
                "sha256": "6f84309a32fa95df674e20a2c305ef5552d98306e7068d4217a4cb5bf792f358",
            },
            "issuer": {
                "commonname": "GTS CA 1O1",
                "country": "US",
                "organization": "Google Trust Services",
            },
            "keyusage": ["critical", "digitalSignature"],
            "publickey": {"algorithm": "id-ecPublicKey"},
            "serial": "7b:03:d2:e3:4b:cb:9f:f4:08:00:00:00:00:13:17:3f",
            "signature": {"algorithm": "sha256WithRSAEncryption"},
            "subject": {
                "altname": ["mail.google.com", "inbox.google.com"],
                "commonname": "mail.google.com",
            },
            "validity": {
                "notafter": "2019-11-28T20:18:56.000Z",
                "notbefore": "2019-09-05T20:18:56.000Z",
            },
            "version": "v3",
            "wildcard": "false",
        },
        {
            "@category": "ctl",
            "@timestamp": "2019-09-15T15:42:32.000Z",
            "@type": "doc",
            "country": "US",
            "domain": "google.com",
            "hostname": ["www.google.com"],
            "ip": ["216.58.206.228", "2a00:1450:4007:817:0:0:0:2004"],
            "organization": "Google LLC",
            "seen_date": "2019-09-15",
            "source": "Google Rocketeer",
            "host": "www",
            "tld": "com",
            "basicconstraints": ["critical"],
            "ca": "false",
            "extkeyusage": ["serverAuth"],
            "fingerprint": {
                "md5": "465d3ea2b4724904cca90e28554232e7",
                "sha1": "e370d85559f90b64dad4522255acc12357d4a3c6",
                "sha256": "36302747c8711a01b40eb3832da9f77c7076441631ee9370091cbd30c2737f17",
            },
            "issuer": {
                "commonname": "GTS CA 1O1",
                "country": "US",
                "organization": "Google Trust Services",
            },
            "keyusage": ["critical", "digitalSignature"],
            "publickey": {"algorithm": "id-ecPublicKey"},
            "serial": "01:a7:8a:7f:5e:bb:b7:ba:02:00:00:00:00:42:ff:ed",
            "signature": {"algorithm": "sha256WithRSAEncryption"},
            "subject": {"altname": ["www.google.com"], "commonname": "www.google.com"},
            "validity": {
                "notafter": "2019-11-28T20:21:24.000Z",
                "notbefore": "2019-09-05T20:21:24.000Z",
            },
            "version": "v3",
            "wildcard": "false",
        },
        {
            "@category": "ctl",
            "@timestamp": "2019-09-15T15:42:32.000Z",
            "@type": "doc",
            "country": "US",
            "ip": [
                "216.58.206.237",
                "2a00:1450:4007:817:0:0:0:200d",
                "216.58.201.238",
                "2a00:1450:4007:816:0:0:0:200e",
            ],
            "organization": "Google LLC",
            "seen_date": "2019-09-15",
            "source": "Google Rocketeer",
            "domain": ["google.com", "android.com"],
            "hostname": ["accounts.google.com", "partner.android.com"],
            "host": ["partner", "accounts"],
            "tld": "com",
            "basicconstraints": ["critical"],
            "ca": "false",
            "extkeyusage": ["serverAuth"],
            "fingerprint": {
                "md5": "a1e7f197dc13fbee496d70dc81084447",
                "sha1": "248be52b3053522127316f116356600a0cc9a0b3",
                "sha256": "15142fc146b7eb1b3eb170900c58a7c52c0c6b92f231a36adcee046da63b7d4a",
            },
            "issuer": {
                "commonname": "GTS CA 1O1",
                "country": "US",
                "organization": "Google Trust Services",
            },
            "keyusage": ["critical", "digitalSignature", "keyEncipherment"],
            "publickey": {
                "algorithm": "rsaEncryption",
                "exponent": "65537",
                "length": "2048",
            },
            "serial": "04:05:5b:16:d1:97:a4:3a:08:00:00:00:00:13:16:ea",
            "signature": {"algorithm": "sha256WithRSAEncryption"},
            "subject": {
                "altname": ["*.partner.android.com", "accounts.google.com"],
                "commonname": "accounts.google.com",
            },
            "validity": {
                "notafter": "2019-11-28T20:17:02.000Z",
                "notbefore": "2019-09-05T20:17:02.000Z",
            },
            "version": "v3",
            "wildcard": "true",
        },
        {
            "@category": "ctl",
            "@timestamp": "2019-09-15T15:42:27.000Z",
            "@type": "doc",
            "country": "US",
            "domain": "google.com",
            "hostname": ["m.google.com"],
            "ip": ["172.217.18.203", "2a00:1450:4007:805:0:0:0:200b"],
            "organization": "Google LLC",
            "seen_date": "2019-09-15",
            "source": "Google Rocketeer",
            "tld": "com",
            "basicconstraints": ["critical"],
            "ca": "false",
            "extkeyusage": ["serverAuth"],
            "fingerprint": {
                "md5": "273cd737eba0997ecaa2b7e966a3ebfa",
                "sha1": "bdb9f743b270397978cd5fbb366d3e52b68ee56c",
                "sha256": "e4ce27eadeef2e6e89683d5862f44152883a6677250476ace2b4b70dd87bed26",
            },
            "host": "m",
            "issuer": {
                "commonname": "GTS CA 1O1",
                "country": "US",
                "organization": "Google Trust Services",
            },
            "keyusage": ["critical", "digitalSignature", "keyEncipherment"],
            "publickey": {
                "algorithm": "rsaEncryption",
                "exponent": "65537",
                "length": "2048",
            },
            "serial": "2a:90:a6:05:7f:5a:a0:82:08:00:00:00:00:13:17:55",
            "signature": {"algorithm": "sha256WithRSAEncryption"},
            "subject": {"altname": ["m.google.com"], "commonname": "m.google.com"},
            "validity": {
                "notafter": "2019-11-28T20:19:58.000Z",
                "notbefore": "2019-09-05T20:19:58.000Z",
            },
            "version": "v3",
            "wildcard": "false",
        },
    ],
    "status": "ok",
    "took": "0.153",
    "total": 827,
}


@pytest.fixture
def result():
    return ctl_result


@pytest.fixture
def result_page_0():
    return ctl_result


@pytest.fixture
def result_page_1():
    return {}
