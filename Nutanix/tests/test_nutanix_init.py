from nutanix_prism import __version__


def test_import_and_version():
    assert isinstance(__version__, str)
