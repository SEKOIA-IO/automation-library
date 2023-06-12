from unittest.mock import Mock, patch

import pytest

from gitmodule.repository import GitRepository
from gitmodule.triggers.new_commit import NewCommitTrigger


@pytest.fixture
def trigger(symphony_storage):
    trigger = NewCommitTrigger(data_path=symphony_storage)
    trigger.module.configuration = {"repository_url": "https://github.com/SEKOIA-IO/test_repo.git"}
    trigger.log = Mock()

    return trigger


def test_trigger_init(dummy_repo, trigger):
    trigger._init_repository()
    assert trigger._last_commit == "f4176e56568797201e530b4309c57815c92d6de7"


@patch.object(GitRepository, "pull")
@patch.object(NewCommitTrigger, "send_event")
def test_trigger_run_no_new_commit(send_event, pull, dummy_repo, trigger):
    trigger._init_repository()
    trigger._run()

    send_event.assert_not_called()


@patch.object(GitRepository, "pull")
@patch.object(NewCommitTrigger, "send_event")
def test_trigger_run_new_commit(send_event, pull, dummy_repo, trigger, settings):
    repository_directory = settings.repository_directory

    # Init the repository and change _last_commit to simulate a new commit
    trigger._init_repository()
    trigger._last_commit = "9b99e4b5e854f6641b92f597196e7fa4b14d9db9"

    # Run the trigger, it should send a commit
    trigger._run()

    pull.assert_called_with()
    send_event.assert_called_with(
        "Commit: Update README.md",
        {
            "commit": {
                "hexsha": "dba049df562e492426a76303538cbc9fb20de7b9",
                "summary": "Update README.md",
                "message": "Update README.md\n",
                "author_name": "SEKOIA-IO",
                "author_email": "integration@sekoia.io",
                "datetime": 1673964131,
            },
            "repository_path": repository_directory,
        },
        repository_directory,
    )


@patch.object(GitRepository, "pull")
@patch.object(NewCommitTrigger, "send_event")
def test_trigger_run_two_new_commits(send_event, pull, dummy_repo, trigger):
    # Init the repository and change _last_commit to simulate two new commits
    trigger._init_repository()
    trigger._last_commit = "b26fd50e937871c068e9560f78abd6b9dc6ceae7"

    # Run the trigger, it should send two commits
    trigger._run()
    assert send_event.call_count == 3

    # Calling it again should not send any commit
    send_event.reset_mock()
    trigger._run()
    assert send_event.call_count == 0


def test_trigger_sleep_time(trigger):
    trigger.configuration = {}
    assert trigger.sleep_time == 300

    trigger.configuration = {"sleep_time": 5}
    assert trigger.sleep_time == 5
