import pytest
import requests

import api.client
from api.client import ApiClient, ApiError
from config.settings import Settings


pytestmark = [pytest.mark.api, pytest.mark.unit]


SYNTHETIC_BODY = "synthetic-response-body-must-not-leak"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.text = text
        self._payload = payload

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._payload is None:
            raise ValueError("not json")

        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.headers = {}
        self.calls = []
        self.closed = False
        self._response = response
        self._error = error

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})

        if self._error:
            raise self._error

        return self._response

    def close(self):
        self.closed = True


def make_client(session):
    return ApiClient(
        base_url="https://api.example.test/",
        timeout=5,
        session=session
    )


# Validate that get_resource requests the complete collection with a timeout
@pytest.mark.smoke
def test_get_resource_requests_full_collection():
    session = FakeSession(FakeResponse(payload={"users": [], "total": 0}))

    payload = make_client(session).get_resource("users")

    assert payload == {"users": [], "total": 0}
    assert session.calls == [{
        "url": "https://api.example.test/users",
        "params": {"limit": 0},
        "timeout": 5
    }]


# Validate that the client falls back to centralized settings. Distinct,
# injected values prove they come from the settings, not from a default.
@pytest.mark.regression
def test_client_uses_centralized_settings(monkeypatch):
    settings = Settings(
        api_base_url="https://settings.example.test/",
        api_timeout=12.5,
        db_connect_timeout=3
    )
    monkeypatch.setattr(api.client, "get_settings", lambda: settings)

    client = ApiClient(session=FakeSession())

    assert client.base_url == "https://settings.example.test"
    assert client.timeout == 12.5


# Validate that JSON is requested explicitly
def test_client_sets_accept_json_header():
    session = FakeSession()

    make_client(session)

    assert session.headers["Accept"] == "application/json"


# Validate that HTTP errors expose the status code but never the response body
# (one client error and one server error: both take the same code path)
@pytest.mark.parametrize("status_code", [401, 503])
@pytest.mark.regression
def test_http_error_hides_response_body(status_code):
    session = FakeSession(FakeResponse(status_code=status_code, text=SYNTHETIC_BODY))

    with pytest.raises(ApiError) as error:
        make_client(session).get_resource("users")

    assert error.value.status_code == status_code
    assert error.value.resource == "users"
    assert str(status_code) in str(error.value)
    assert SYNTHETIC_BODY not in str(error.value)


# Validate that timeouts raise a safe ApiError without the original exception chain
@pytest.mark.regression
def test_timeout_raises_safe_error():
    session = FakeSession(error=requests.Timeout("https://api.example.test/users"))

    with pytest.raises(ApiError) as error:
        make_client(session).get_resource("users")

    assert "timed out" in str(error.value)
    assert "https://" not in str(error.value)
    assert error.value.__suppress_context__ is True


# Validate that connection errors do not leak URLs or embedded credentials
@pytest.mark.regression
def test_connection_error_hides_url():
    session = FakeSession(
        error=requests.ConnectionError("https://synthetic-user:synthetic-pass@host")
    )

    with pytest.raises(ApiError) as error:
        make_client(session).get_resource("users")

    message = str(error.value)

    assert "ConnectionError" in message
    assert "synthetic-user" not in message
    assert "synthetic-pass" not in message


# Validate that a non-JSON body raises a safe ApiError
@pytest.mark.regression
def test_invalid_json_raises_safe_error():
    session = FakeSession(FakeResponse(payload=None, text=SYNTHETIC_BODY))

    with pytest.raises(ApiError) as error:
        make_client(session).get_resource("products")

    assert "not valid JSON" in str(error.value)
    assert SYNTHETIC_BODY not in str(error.value)


# Validate that the context manager closes the HTTP session
def test_context_manager_closes_session():
    session = FakeSession()

    with make_client(session):
        assert session.closed is False

    assert session.closed is True
