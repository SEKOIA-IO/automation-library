import json
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

import pytest

from rss.trigger_rss import RSSTrigger


@pytest.fixture
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


@pytest.fixture
def nasa_result():
    return {
        "source": {
            "title": "NASA Breaking News",
            "subtitle": "A RSS news feed containing the latest NASA news articles and press releases.",
            "link": "http://www.nasa.gov/",
            "language": "en-us",
            "author": "jim.wilson@nasa.gov",
            "publisher": "brian.dunbar@nasa.gov",
        },
        "item": {
            "title": "Commercial Space Ride Secured for NASA’s New Air Pollution Sensor",
            "link": "http://www.nasa.gov/press-release/"
            "commercial-space-ride-secured-for-nasa-s-new-air-pollution-sensor",
            "published": "Mon, 22 Jul 2019 18:34 EDT",
            "description": "NASA has secured a host satellite provider and ride into space for an instrument "
            "that will"
            "\n                dramatically advance our understanding of air quality over North America.",
        },
    }


@pytest.fixture()
def atom_result():
    return {
        "source": {
            "title": "Example Feed",
            "link": "http://example.org/",
            "author": "John Doe",
        },
        "item": {
            "title": "Atom-Powered Robots Run Amok",
            "link": "http://example.org/2003/12/13/atom03",
            "published": "2003-12-13T18:30:02Z",
            "description": "Some text.",
        },
    }


@patch.object(RSSTrigger, "send_event")
@patch.object(RSSTrigger, "log")
def test_rss_trigger_nasa(_, send_event_mock, symphony_storage, nasa_result):
    trigger = RSSTrigger(data_path=symphony_storage)

    trigger._run("tests/nasa.xml")

    send_event_mock.assert_any_call(event_name="RSS feed tests/nasa.xml", event=nasa_result)
    assert send_event_mock.call_count == 10

    # Calling it a second time should not send events because there was nothing new
    trigger._run("tests/nasa.xml")
    assert send_event_mock.call_count == 10


@patch.object(RSSTrigger, "send_event")
@patch.object(RSSTrigger, "log")
def test_atom_trigger(_, send_event_mock, symphony_storage, atom_result):
    trigger = RSSTrigger(data_path=symphony_storage)

    trigger._run("tests/atom.xml")

    send_event_mock.assert_any_call(event_name="RSS feed tests/atom.xml", event=atom_result)
    assert send_event_mock.call_count == 1

    # Calling it a second time should not send events because there was nothing new
    trigger._run("tests/atom.xml")
    assert send_event_mock.call_count == 1


@patch.object(RSSTrigger, "send_event")
@patch.object(RSSTrigger, "log")
def test_trigger_to_file(_, send_event_mock, symphony_storage, atom_result, settings):
    # clear the cache
    rmtree(settings.cache_dir)

    # initialize the trigger
    trigger = RSSTrigger(data_path=symphony_storage)

    trigger._run("tests/atom.xml", to_file=True)

    assert send_event_mock.call_count == 1
    file_path = symphony_storage / send_event_mock.call_args[1]["directory"] / "event.json"
    with file_path.open() as fp:
        loaded = json.load(fp)
    assert loaded == atom_result
