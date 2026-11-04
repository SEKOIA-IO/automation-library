import pytest
import requests_mock

from slack_modules.client import AuditLogsClient
from slack_modules.errors import AuthenticationError, PlanError, SlackAuditLogsError

BASE_URL = "https://api.slack.test/audit/v1"


def make_client(**kwargs):
    return AuditLogsClient(base_url=BASE_URL, token="xoxp-test", **kwargs)


def entry(event_id: str, date_create: int = 1_700_000_000) -> dict:
    return {"id": event_id, "date_create": date_create, "action": "user_login"}


def ids(pages) -> list[list[str]]:
    return [[event["id"] for event in entries] for entries, _ in pages]


def test_single_page_is_yielded_and_iteration_stops():
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{BASE_URL}/logs",
            json={"entries": [entry("a"), entry("b")], "response_metadata": {"next_cursor": ""}},
        )

        pages = list(make_client().iter_pages(oldest=1_700_000_000, latest=1_700_003_599))

    assert ids(pages) == [["a", "b"]]
    assert pages[0][1] == ""  # an empty cursor: the window is drained


def test_latest_is_sent_alongside_oldest():
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json={"entries": [entry("a")], "response_metadata": {"next_cursor": ""}})

        list(make_client().iter_pages(oldest=1_700_000_000, latest=1_700_003_599, limit=500))

    assert mock.request_history[0].qs["oldest"] == ["1700000000"]
    assert mock.request_history[0].qs["latest"] == ["1700003599"]


def test_a_given_cursor_is_sent_on_the_very_first_request():
    """How a window half-read by an earlier cycle is picked up: the caller hands back the cursor it
    stored, and the walk continues from there instead of from the window's first page."""
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json={"entries": [entry("c")], "response_metadata": {"next_cursor": ""}})

        pages = list(make_client().iter_pages(oldest=1, latest=2, cursor="stored-cursor"))

    assert mock.request_history[0].qs["cursor"] == ["stored-cursor"]
    assert ids(pages) == [["c"]]


def test_each_page_yields_the_cursor_that_came_with_it():
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{BASE_URL}/logs",
            [
                {"json": {"entries": [entry("a")], "response_metadata": {"next_cursor": "one"}}},
                {"json": {"entries": [entry("b")], "response_metadata": {"next_cursor": "two"}}},
                {"json": {"entries": [entry("c")], "response_metadata": {"next_cursor": ""}}},
            ],
        )

        pages = list(make_client().iter_pages(oldest=1, latest=2))

    assert [cursor for _, cursor in pages] == ["one", "two", ""]


def test_an_empty_page_is_still_yielded_so_its_cursor_is_not_lost():
    """Skipping a page that carries no entries would throw away the cursor that came with it, and
    the caller would later resume from a staler one."""
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{BASE_URL}/logs",
            [
                {"json": {"entries": [], "response_metadata": {"next_cursor": "keep-going"}}},
                {"json": {"entries": [entry("a")], "response_metadata": {"next_cursor": ""}}},
            ],
        )

        pages = list(make_client().iter_pages(oldest=1, latest=2))

    assert pages[0] == ([], "keep-going")
    assert ids(pages) == [[], ["a"]]


def test_cursor_is_followed_until_it_is_empty():
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{BASE_URL}/logs",
            [
                {"json": {"entries": [entry("a")], "response_metadata": {"next_cursor": "next"}}},
                {"json": {"entries": [entry("b")], "response_metadata": {"next_cursor": ""}}},
            ],
        )

        client = make_client()
        pages = list(client.iter_pages(oldest=1_700_000_000, latest=1_700_003_599, limit=1))

    assert ids(pages) == [["a"], ["b"]]
    assert mock.request_history[0].qs["oldest"] == ["1700000000"]
    assert mock.request_history[0].qs["limit"] == ["1"]
    assert "cursor" not in mock.request_history[0].qs
    assert mock.request_history[1].qs["cursor"] == ["next"]
    # the window travels with the cursor, so a page never widens past its sub-window
    assert mock.request_history[1].qs["latest"] == ["1700003599"]
    assert mock.request_history[0].headers["Authorization"] == "Bearer xoxp-test"


def test_iteration_stops_when_the_response_carries_no_metadata():
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json={"entries": [entry("a")]})

        pages = list(make_client().iter_pages(oldest=1, latest=2))

    assert ids(pages) == [["a"]]
    assert pages[0][1] == ""


def test_authentication_error_is_raised_on_http_401():
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", status_code=401, json={"ok": False, "error": "not_authed"})

        with pytest.raises(AuthenticationError, match="not_authed"):
            list(make_client().iter_pages(oldest=1, latest=2))


def test_authentication_error_is_raised_on_an_ok_false_body():
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json={"ok": False, "error": "missing_scope"})

        with pytest.raises(AuthenticationError, match="missing_scope"):
            list(make_client().iter_pages(oldest=1, latest=2))


def test_plan_error_is_raised_when_the_tenant_is_not_enterprise_grid():
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json={"ok": False, "error": "paid_only"})

        with pytest.raises(PlanError, match="paid_only"):
            list(make_client().iter_pages(oldest=1, latest=2))


def test_unexpected_status_is_wrapped_in_the_module_error():
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", status_code=500, text="boom")

        with pytest.raises(SlackAuditLogsError):
            list(make_client().iter_pages(oldest=1, latest=2))


def test_non_json_body_is_wrapped_in_the_module_error():
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", text="<html>maintenance</html>")

        with pytest.raises(SlackAuditLogsError):
            list(make_client().iter_pages(oldest=1, latest=2))


def test_a_json_body_that_is_not_an_object_is_wrapped_in_the_module_error():
    """A list or a bare string decodes fine, so the ValueError guard above never fires; without a
    shape check the caller would meet an AttributeError instead of a handled API failure."""
    with requests_mock.Mocker() as mock:
        mock.get(f"{BASE_URL}/logs", json=["not", "an", "object"])

        with pytest.raises(SlackAuditLogsError):
            list(make_client().iter_pages(oldest=1, latest=2))


def test_the_budget_ending_on_a_drained_page_still_reports_the_window_as_drained():
    """The boundary that separates an unfinished window from a finished one: at exactly MAX_PAGES
    pages the client returns normally either way, and only the last cursor says which happened.
    This is the drained half - the pending half is the test below."""
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{BASE_URL}/logs",
            [
                {"json": {"entries": [entry("a")], "response_metadata": {"next_cursor": "next"}}},
                {"json": {"entries": [entry("b")], "response_metadata": {"next_cursor": ""}}},
            ],
        )

        client = make_client()
        client.MAX_PAGES = 2
        pages = list(client.iter_pages(oldest=1, latest=2))

    assert ids(pages) == [["a"], ["b"]]
    assert pages[-1][1] == ""  # drained, even though it took the whole budget to get there


def test_the_page_budget_stops_the_walk_and_leaves_its_cursor_pending():
    """Running out of budget is not an error any more: the last cursor yielded is still non-empty,
    which is how the caller knows the window is unfinished and where to resume it."""
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{BASE_URL}/logs",
            json={"entries": [entry("a")], "response_metadata": {"next_cursor": "always-more"}},
        )

        client = make_client()
        client.MAX_PAGES = 3
        pages = list(client.iter_pages(oldest=1, latest=2))

    assert len(pages) == 3
    assert pages[-1][1] == "always-more"
