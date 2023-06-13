import os
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from gitmodule.repository import GitRepository
from gitmodule.triggers.file_changes import FileChangesTrigger, filechanges_directory, safe_join


@pytest.fixture
def trigger(symphony_storage):
    trigger = FileChangesTrigger(data_path=symphony_storage)
    trigger.module.configuration = {"repository_url": "https://github.com/SEKOIA-IO/test_repo.git"}
    trigger.configuration = {}
    trigger.log = Mock()

    return trigger


@patch.object(GitRepository, "pull")
@patch.object(FileChangesTrigger, "send_event")
def test_trigger_run_no_new_commit(send_event, pull, dummy_repo, trigger):
    trigger._init_repository()
    trigger._run()

    send_event.assert_not_called()


@patch.object(GitRepository, "pull")
@patch.object(FileChangesTrigger, "send_event")
def test_trigger_run_new_commit(send_event, pull, dummy_repo, trigger, settings):
    # Init the repository and change _last_commit to simulate a new commit
    trigger._init_repository()
    trigger._last_commit = "9b99e4b5e854f6641b92f597196e7fa4b14d9db9"

    # Run the trigger, it should send a commit
    trigger._run()

    pull.assert_called_with()

    send_event.assert_called_with(
        "1 file changes",
        {
            "changes": [{"filepath": "README.md", "change_type": "M"}],
            "new_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "old_commit": "9b99e4b5e854f6641b92f597196e7fa4b14d9db9",
            "repository_path": "test_repo",
        },
        settings.repository_directory,
        remove_directory=False,
    )


@patch.object(GitRepository, "pull")
@patch.object(FileChangesTrigger, "send_event")
def test_trigger_run_two_new_commits(send_event, pull, dummy_repo, trigger, settings):
    # Init the repository and change _last_commit to simulate two new commits
    trigger._init_repository()
    trigger._last_commit = "b26fd50e937871c068e9560f78abd6b9dc6ceae7"

    # Run the trigger, it should combine files from both commits
    trigger._run()
    send_event.assert_called_with(
        "2 file changes",
        {
            "changes": [
                {"filepath": "README.md", "change_type": "M"},
                {"filepath": "directory/some_file.txt", "change_type": "A"},
            ],
            "new_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "old_commit": "b26fd50e937871c068e9560f78abd6b9dc6ceae7",
            "repository_path": "test_repo",
        },
        settings.repository_directory,
        remove_directory=False,
    )

    # Calling it again should not send any commit
    trigger._run()
    assert send_event.call_count == 1


@patch.object(GitRepository, "pull")
@patch.object(FileChangesTrigger, "send_event")
def test_trigger_run_chunks(send_event, pull, dummy_repo, trigger, settings):
    # Set chunk_size to 1 to force chunked results
    trigger.configuration = {"chunk_size": 1}

    # Init the repository and change _last_commit to simulate two new commits
    trigger._init_repository()
    trigger._last_commit = "b26fd50e937871c068e9560f78abd6b9dc6ceae7"

    # Run the trigger, it should generate two separate events
    trigger._run()

    call1 = call(
        "1 file changes",
        {
            "changes": [{"filepath": "README.md", "change_type": "M"}],
            "new_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "old_commit": "b26fd50e937871c068e9560f78abd6b9dc6ceae7",
            "repository_path": "test_repo",
        },
        settings.repository_directory,
        remove_directory=False,
    )
    call2 = call(
        "1 file changes",
        {
            "changes": [
                {"filepath": "directory/some_file.txt", "change_type": "A"},
            ],
            "new_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "old_commit": "b26fd50e937871c068e9560f78abd6b9dc6ceae7",
            "repository_path": "test_repo",
        },
        settings.repository_directory,
        remove_directory=False,
    )

    send_event.assert_has_calls([call1, call2])


@patch.object(FileChangesTrigger, "send_event")
def test_trigger_send_initial_state_not_cloned(send_event, dummy_repo, trigger):
    trigger.configuration = {"send_initial_state": True}
    trigger._init_repository()

    # This should have created an event with all existing files
    send_event.assert_not_called()


original_clone = GitRepository.clone


def mocked_clone(self):
    original_clone(self)

    return True


@patch.object(GitRepository, "clone", new=mocked_clone)
@patch.object(FileChangesTrigger, "send_event")
def test_trigger_send_initial_state(send_event, dummy_repo, trigger, settings):
    trigger.configuration = {"send_initial_state": True}
    trigger._init_repository()

    # This should have created an event with all existing files
    send_event.assert_called_with(
        "2 file changes",
        {
            "changes": [
                {"filepath": "README.md", "change_type": "A"},
                {"filepath": "directory/some_file.txt", "change_type": "A"},
            ],
            "new_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "old_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "repository_path": "test_repo",
        },
        settings.repository_directory,
        remove_directory=False,
    )


@patch.object(GitRepository, "clone", new=mocked_clone)
@patch.object(FileChangesTrigger, "send_event")
def test_trigger_file_filter(send_event, dummy_repo, trigger, settings):
    trigger.configuration = {"send_initial_state": True, "filter": "*.txt"}
    trigger._init_repository()

    # This should have created an event with all textual files
    send_event.assert_called_with(
        "1 file changes",
        {
            "changes": [
                {"filepath": "directory/some_file.txt", "change_type": "A"},
            ],
            "new_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "old_commit": "f4176e56568797201e530b4309c57815c92d6de7",
            "repository_path": "test_repo",
        },
        settings.repository_directory,
        remove_directory=False,
    )


@patch.object(GitRepository, "clone", new=mocked_clone)
@patch.object(FileChangesTrigger, "send_event")
def test_trigger_do_not_include_repository(send_event, dummy_repo, trigger, symphony_storage):
    trigger.configuration = {
        "send_initial_state": True,
        "filter": "*.txt",
        "include_repository": False,
    }
    trigger._init_repository()

    # This should have created an event with all existing files
    send_event.assert_called_once()
    (name, event, directory), kwargs = send_event.call_args

    assert name == "1 file changes"
    assert event["changes"] == [
        {"filepath": "directory/some_file.txt", "change_type": "A"},
    ]
    assert event["new_commit"] == "f4176e56568797201e530b4309c57815c92d6de7"
    assert event["old_commit"] == "f4176e56568797201e530b4309c57815c92d6de7"
    assert kwargs["remove_directory"] is True
    assert directory.startswith(filechanges_directory())

    # Make sure files exist
    assert (symphony_storage / directory / "directory/some_file.txt").is_file()


def test_config_bool_as_string(symphony_storage):
    # Make sure bool as strings work as expected
    trigger = FileChangesTrigger(data_path=symphony_storage)
    trigger.configuration = {
        "send_initial_state": "False",
        "include_repository": "False",
    }
    assert trigger.send_initial_state is False
    assert trigger.include_repository is False

    trigger = FileChangesTrigger(data_path=symphony_storage)
    trigger.configuration = {"send_initial_state": "True", "include_repository": "True"}
    assert trigger.send_initial_state is True
    assert trigger.include_repository is True

    # Make sure default values are as expected
    trigger = FileChangesTrigger()
    trigger.configuration = {}
    assert trigger.send_initial_state is False
    assert trigger.include_repository is True


def test_safe_join():
    base = Path("/test/dir")
    assert safe_join(base, "part").as_posix() == "/test/dir/part"

    with pytest.raises(ValueError):
        safe_join(base, "../hacker")


@pytest.mark.skipif(
    "{'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_BUCKET_NAME', 'AWS_DEFAULT_REGION'} \
    .issubset(os.environ.keys()) == False"
)
def test_safe_join_with_remote_storage(remote_storage):
    assert safe_join(remote_storage, "part").as_posix() == f"/{os.environ['AWS_BUCKET_NAME']}/part"

    with pytest.raises(ValueError):
        safe_join(remote_storage, "../hacker")
