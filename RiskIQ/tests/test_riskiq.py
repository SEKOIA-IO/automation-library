from riskiq_module import SslCertificateBySha1Action


def test_riskiq():
    assert SslCertificateBySha1Action.verb == "get"
    assert SslCertificateBySha1Action.query_parameters == ["sha1"]
