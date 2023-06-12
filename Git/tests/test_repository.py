from shutil import copytree, rmtree
from unittest.mock import patch

import git
import pytest


@pytest.fixture
def gitrepository(settings):
    from gitmodule.repository import GitRepository

    yield GitRepository


def test_repository_repo_name(gitrepository):
    # Repository URL ending with .git
    repository = gitrepository("https://github.com/User/Repository.git")
    assert repository._get_repo_name() == "Repository"

    # Repository URL without .git
    repository = gitrepository("https://github.com/User/Repository")
    assert repository._get_repo_name() == "Repository"


@pytest.mark.connected
def test_clone(symphony_storage, settings, gitrepository):
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git", data_path=symphony_storage)
    repository.clone()

    assert isinstance(repository._repo, git.Repo)
    assert (repository.path / "README.md").is_file()
    assert (symphony_storage / settings.repository_directory / "README.md").is_file()


def test_clone_mocked(clone_mock, gitrepository):
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git")
    repository.clone()

    clone_mock.assert_called_with("https://github.com/SEKOIA-IO/test_repo.git", repository.path.as_posix())


def test_clone_should_not_clone_when_repo_exists(gitrepository):
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git")
    repository.clone()

    with patch.object(git.Repo, "clone_from") as clone_mock:
        repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git")
        repository.clone()

        assert isinstance(repository._repo, git.Repo)
        assert (repository.path / "README.md").is_file()
        clone_mock.assert_not_called()


def test_last_commit(gitrepository):
    # Clone the respository
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git")
    repository.clone()

    # Check last commit
    repository.last_commit().hexsha == "f4176e56568797201e530b4309c57815c92d6de7"


def test_getattr(gitrepository):
    # Clone the repository
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git")
    repository.clone()

    # Access git.Repo properties directly
    assert repository.active_branch.name == "main"


def test_clone_with_recovering_from_storage(symphony_storage, clone_mock, settings, gitrepository):
    # arrange
    repopath = settings.module_directory / settings.repository_directory / "test_repo"
    if repopath.is_dir():
        rmtree(repopath)
    copytree(
        "tests/data/test_repo/dot_git",
        symphony_storage / settings.repository_directory / ".git",
        dirs_exist_ok=True,
    )

    # act
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git", data_path=symphony_storage)
    repository.clone()

    # assert
    clone_mock.assert_not_called()


def test_pull_with_backup_to_storage(symphony_storage, gitrepository):
    # arrange
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git", data_path=symphony_storage)
    repository.clone()

    # act
    with patch("gitmodule.utils.copytree") as copytree_mock:
        repository.pull()

        # assert
        copytree_mock.assert_called()


def test_pull_with_no_storage(gitrepository):
    # arrange
    repository = gitrepository("https://github.com/SEKOIA-IO/test_repo.git")
    repository.clone()

    # act
    with patch("gitmodule.utils.copytree") as copytree_mock:
        repository.pull()

        # assert
        copytree_mock.assert_not_called()
