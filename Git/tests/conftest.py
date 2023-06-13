import os
from shutil import copyfile, copytree, rmtree
from unittest.mock import patch

import boto3
import git
import pytest
from s3path import S3Path, register_configuration_parameter


@pytest.fixture(autouse=True)
def purge_settings_lru_cache():
    """Reset Settings’s `lru_cache` before every test to prevent wrong
    usage of cache.

    """

    from gitmodule.settings import get_settings

    get_settings.cache_clear()

    yield


@pytest.fixture
def settings(tmp_path):
    from gitmodule.settings import Settings

    patched_env = {
        "SYMPHONY_GIT_MODULE_DIRECTORY": str(tmp_path),
        "SYMPHONY_GIT_REPOSITORY_DIRECTORY": "repository",
    }

    with patch.dict(os.environ, patched_env):
        (tmp_path / "repository").mkdir(parents=True, exist_ok=True)

        yield Settings()


@pytest.fixture
def symphony_storage(tmp_path):
    new_storage = tmp_path

    yield new_storage

    rmtree(new_storage.as_posix())


@pytest.fixture
def dummy_repo(settings):
    repopath = settings.module_directory / settings.repository_directory / "test_repo"

    # Copy the test repository and rename the `dot_git` directory
    # so that the result if valid.
    #
    # We had to rename the directory in order to be able to add it
    # to the repository

    # remove path if exists
    if repopath.is_dir():
        rmtree(repopath)

    copytree("tests/data/test_repo/", repopath, dirs_exist_ok=True)
    (repopath / "dot_git").rename(repopath / ".git")

    yield repopath


@pytest.fixture
def light_repo(symphony_storage):
    (symphony_storage / "directory").mkdir(parents=True, exist_ok=True)
    copyfile("tests/data/test_repo/README.md", symphony_storage / "README.md")
    copyfile(
        "tests/data/test_repo/directory/some_file.txt",
        symphony_storage / "directory/some_file.txt",
    )

    yield symphony_storage


@pytest.fixture
def clone_mock():
    with patch.object(git.Repo, "clone_from") as mock:
        yield mock


@pytest.fixture
def remote_storage():
    boto3.setup_default_session(
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ["AWS_DEFAULT_REGION"],
    )
    base_path = S3Path(f"/{os.environ['AWS_BUCKET_NAME']}")

    stack_resource = boto3.resource("s3", endpoint_url=os.environ["AWS_S3_ENDPOINT_URL"])
    register_configuration_parameter(base_path, resource=stack_resource)

    yield base_path
