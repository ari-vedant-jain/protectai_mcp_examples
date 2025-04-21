"""Auth providers for the Layer SDK."""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional

import orjson
import requests

from .logger import logger
from .exceptions import (
    LayerAuthError,
    LayerHTTPError,
    LayerRequestError,
    LayerMissingRequiredConfigurationError,
)
from ._default_client import _create_default_http_session


class AuthProvider(ABC):
    """Abstract class for authentication providers.

    Implementations should provide a method to get the headers to be used in the request.
    """

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get the headers to be used in the request.

        Returns:
            Dict[str, str]: A dictionary of headers
        """
        pass


class OIDCClientCredentials(AuthProvider):
    """OIDC Client Credentials authentication provider.

    This provider uses the client credentials flow to obtain an access token.
    It is tested with Keycloak but can work with more providers.

    Args:
        token_url (str): The token URL to use to obtain the access token
        client_id (str): The client ID to use to obtain the access token
        client_secret (str): The client secret to use to obtain the access token
        scope (str): The scope to use to obtain the access token
        http_session (requests.Session): The HTTP client to use to make requests
        http_timeout (int): The timeout to use for the HTTP requests
    """

    _client_id: str
    _client_secret: str
    _token_url: str
    _access_token: Optional[str]
    _expires_at: float
    _token_type: str
    _scope: Optional[str]
    _http_session: requests.Session
    _http_timeout: int

    def __init__(
        self,
        *,
        token_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
        http_session: Optional[requests.Session] = None,
        http_timeout: Optional[int] = None,
    ):
        """Initialize the OIDC Client Credentials authentication provider.

        Args:
            token_url (str): The token URL to use to obtain the access token
                e.g. https://keycloak.example.com/auth/realms/myrealm/protocol/openid-connect/token
            client_id (str): The client ID to use to obtain the access token
            client_secret (str): The client secret to use to obtain the access token
            scope (str): The scope to use to obtain the access token e.g. layer-sdk
            http_session (requests.Session): The HTTP client to use to make requests.
                By default, it uses a pre-configured session with retries and pool.
            http_timeout (int): The timeout to use for the HTTP requests.
                By default, it uses 10 seconds.

        Raises:
            LayerMissingRequiredConfigurationError: If any of the required arguments are missing
        """
        token_url = token_url or os.getenv("LAYER_OIDC_TOKEN_URL")
        if not token_url:
            raise LayerMissingRequiredConfigurationError("Missing required argument `token_url`")
        self._token_url = token_url

        client_id = client_id or os.getenv("LAYER_OIDC_CLIENT_ID")
        if not client_id:
            raise LayerMissingRequiredConfigurationError("Missing required argument `client_id`")
        self._client_id = client_id

        client_secret = client_secret or os.getenv("LAYER_OIDC_CLIENT_SECRET")
        if not client_secret:
            raise LayerMissingRequiredConfigurationError(
                "Missing required argument `client_secret`"
            )
        self._client_secret = client_secret

        self._scope = scope or os.getenv("LAYER_OIDC_SCOPE")
        self._access_token = None
        self._expires_at = 0.0
        self._token_type = "Bearer"

        if not http_session:
            http_session = _create_default_http_session()
        self._http_session = http_session

        self._http_timeout = http_timeout or int(os.getenv("LAYER_OIDC_TIMEOUT", 10))

        logger.debug(
            f"OIDCClientCredentials initialized with "
            f"token_url={self._token_url}, scope={self._scope}"
        )

    def _refresh_token(self):
        """Refresh the access token.

        Raises:
            LayerHTTPError: If the request to refresh the token fails
        """
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        if self._scope:
            data["scope"] = self._scope

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = self._http_session.post(
                self._token_url, data=data, headers=headers, timeout=self._http_timeout
            )
        except requests.RequestException as e:
            logger.error(f"Failed request to refresh token: {e}")
            raise LayerRequestError(f"Failed request to refresh token: {e}")

        if response.status_code == 401 or response.status_code == 403:
            logger.error(
                f"Failed to refresh token: " 
                f"{response.status_code} {response.content.decode('utf-8')}"
            )
            raise LayerAuthError(
                f"Failed to refresh token {response.status_code}: "
                f"{response.content.decode('utf-8')}"
            )

        if response.status_code != 200:
            logger.error(
                f"Failed request to refresh token: "
                f"{response.status_code} {response.content.decode('utf-8')}"
            )
            raise LayerHTTPError(
                "Failed request refresh token",
                response.status_code,
                response.content.decode("utf-8"),
            )

        token_data = orjson.loads(response.content)
        self._access_token = token_data["access_token"]
        self._token_type = token_data["token_type"] or self._token_type

        if token_data.get("expires_in"):
            logger.debug(f"Token refreshed, expires in {token_data['expires_in']} seconds")
            self._expires_at = (
                time.time() + token_data["expires_in"] - 60
            )  # Refresh 1 minute before expiration

    def get_headers(self) -> Dict[str, str]:
        """Get the headers to be used in the request.

        Raises:
            LayerHTTPError: If the request to refresh the token fails

        Returns:
            Dict[str, str]: A dictionary of headers
        """
        if 0 < self._expires_at < time.time() or not self._access_token:
            logger.debug("Token expired or not set, refreshing")
            self._refresh_token()

        return {"Authorization": f"{self._token_type} {self._access_token}"}
