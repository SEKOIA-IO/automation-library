def test_alert_add_comment(connector, mock_api):
    connector.alert_add_comment("A20", "Looks suspicious")
    mock_api.alert.create_comment.assert_called_once_with(
        alert_id="A20", message="Looks suspicious"
    )


def test_alert_add_observables(connector, mock_api):
    # Mock the create_observable method
    mock_api.alert.create_observable.side_effect = [
        {"id": "OBS1"}, {"id": "OBS2"}
    ]
    observables = [
        {"dataType": "ip", "data": "1.2.3.4"},
        {"dataType": "domain", "data": "evil.com"},
    ]

    result = connector.alert_add_observables("A21", observables)

    # It should call create_observable twice
    assert mock_api.alert.create_observable.call_count == 2
    mock_api.alert.create_observable.assert_any_call(
        alert_id="A21", observable={"dataType": "ip", "data": "1.2.3.4"}, observable_path=None
    )
    mock_api.alert.create_observable.assert_any_call(
        alert_id="A21", observable={"dataType": "domain", "data": "evil.com"}, observable_path=None
    )

    # And return the list of responses
    assert result == [{"id": "OBS1"}, {"id": "OBS2"}]
