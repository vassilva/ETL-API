"""
Reusable HTTP client for the source REST API.

Owns the base URL, timeout, session, status validation and safe error
handling. Error messages never include response bodies or full URLs.
"""

import requests

from config.settings import get_settings


DEFAULT_HEADERS = {"Accept": "application/json"}


class ApiError(RuntimeError):
    """Raised for any failed API request. Contains only safe diagnostics."""

    def __init__(self, resource, reason, status_code=None):
        self.resource = resource
        self.status_code = status_code

        super().__init__(f"API request for '{resource}' failed: {reason}")


class ApiClient:
    def __init__(self, base_url=None, timeout=None, session=None):
        settings = get_settings()

        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.api_timeout
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        self.session.close()

    def get(self, resource, params=None):
        """GET a resource path and return the decoded JSON body."""
        url = f"{self.base_url}/{resource.lstrip('/')}"

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.Timeout:
            raise ApiError(resource, "request timed out") from None
        except requests.RequestException as error:
            raise ApiError(
                resource, f"request error ({type(error).__name__})"
            ) from None

        if not response.ok:
            raise ApiError(
                resource,
                f"unexpected HTTP status {response.status_code}",
                status_code=response.status_code
            )

        try:
            return response.json()
        except ValueError:
            raise ApiError(resource, "response body is not valid JSON") from None

    def get_resource(self, resource):
        """GET the complete collection of a resource (limit=0 = all records)."""
        return self.get(resource, params={"limit": 0})
