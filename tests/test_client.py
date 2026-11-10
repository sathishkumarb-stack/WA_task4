from unittest.mock import Mock, patch

from client import fetch_all


def _response(status_code, payload=None, headers=None):
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_all_uses_offset_pagination():
    session = Mock()
    session.post.return_value = _response(200, {"access_token": "token"})
    session.get.side_effect = [
        _response(200, [{"id": 1}, {"id": 2}], {"X-RateLimit-Remaining": "2"}),
        _response(200, [{"id": 3}], {"X-RateLimit-Remaining": "1"}),
    ]

    result = fetch_all(
        "https://example.test/customers",
        api_key="test-key",
        per_page=2,
        session=session,
    )

    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert "offset=0" in session.get.call_args_list[0].args[0]
    assert "offset=2" in session.get.call_args_list[1].args[0]


def test_fetch_all_refreshes_token_after_401_and_waits_on_rate_limit():
    session = Mock()
    session.post.side_effect = [
        _response(200, {"access_token": "old-token"}),
        _response(200, {"access_token": "new-token"}),
    ]
    session.get.side_effect = [
        _response(401, {"detail": "expired"}),
        _response(200, [{"id": 1}], {"X-RateLimit-Remaining": "0"}),
    ]

    with patch("client.time.sleep") as sleep_mock:
        result = fetch_all(
            "https://example.test/customers",
            api_key="test-key",
            per_page=5,
            session=session,
            sleep_seconds=0.25,
        )

    assert result == [{"id": 1}]
    assert session.post.call_count == 2
    assert session.get.call_count == 2
    sleep_mock.assert_called_once_with(0.25)
