import os
import sys

# Ensure the package can be imported in CI where the project root
# may not be on PYTHONPATH.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nutanix_prism import __version__


def test_import_and_version():
    assert isinstance(__version__, str)
