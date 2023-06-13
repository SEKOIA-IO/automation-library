# coding: utf-8

# third parties
import pytest

# internal
from gitmodule.utils import copytree


def test_copytree(dummy_repo, symphony_storage):
    copytree(dummy_repo, symphony_storage)

    assert (symphony_storage / "README.md").is_file()
    assert (symphony_storage / "root_file.txt").is_file()
    assert (symphony_storage / "directory").is_dir()
    assert (symphony_storage / "directory" / "some_file.txt").is_file()
    assert (symphony_storage / ".git").is_dir()


@pytest.mark.skipif(
    "{'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_BUCKET_NAME', 'AWS_DEFAULT_REGION'} \
    .issubset(os.environ.keys()) == False"
)
def test_copytree_with_remote_storage(light_repo, remote_storage):
    copytree(light_repo, remote_storage)

    assert (remote_storage / "README.md").is_file()
    assert (remote_storage / "directory").is_dir()
    assert (remote_storage / "directory" / "some_file.txt").is_file()
