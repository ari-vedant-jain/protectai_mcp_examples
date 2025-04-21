"""The main entry point for the Layer SDK i.e. the client."""

import os
import json
import uuid
import inspect
from typing import Any, Dict, List, Union, Optional
from datetime import datetime, timezone
from functools import wraps

import orjson
import requests

from .auth import AuthProvider
from .logger import logger
from .schemas import (
    SessionRequest,
    SessionActionKind,
    SessionActionRequest,
    FirewallLookupDecision,
    FirewallSessionLookupResponse,
)
from ._version import __version__
from ._platform import Platform, get_platform, platform_session_attributes
from .exceptions import (
    LayerHTTPError,
    LayerRequestError,
    LayerFirewallException,
    LayerFirewallHTTPError,
    LayerFirewallRequestError,
    LayerFirewallSessionBlocked,
    LayerRequestPreparationError,
    LayerMissingRequiredConfigurationError,
)
from ._default_client import _create_default_http_session
from .instrumentation import instrumentor_instances


class Client:
    """The main entry point for the Layer SDK i.e. the client.

    The client is a singleton class that is responsible
    for initializing the SDK and creating sessions and actions.
    """

    # Singleton instance
    _instance = None
    # Initialization flag
    _initialized: bool
    # Application ID
    _application_id: Union[str, uuid.UUID]
    # Base URL for the Layer API
    _base_url: str
    # Environment
    _environment: Optional[str]
    # Platform
    _platform: Platform
    # Auth provider
    _auth_provider: Optional[AuthProvider]
    # HTTP client session
    _http_session: requests.Session
    # HTTP timeout
    _http_timeout: int
    # Disabled instrumentors
    _disabled_instrumentors: List[str]
    # Firewall Base URL
    _firewall_base_url: Optional[str]
    # Enable firewall instrumentation
    _enable_firewall_instrumentation: bool

    def __new__(cls):
        """Singleton pattern to ensure only one instance of the SDK is created."""
        if cls._instance is None:
            cls._instance = super(Client, cls).__new__(cls)
            cls._instance._initialized = False

        return cls._instance

    def init(
        self,
        *,
        base_url: Optional[str] = None,
        application_id: Optional[Union[str, uuid.UUID]] = None,
        environment: Optional[str] = None,
        auth_provider: Optional[AuthProvider] = None,
        http_session: Optional[requests.Session] = None,
        http_timeout: Optional[int] = None,
        platform: Optional[Platform] = None,
        disabled_instrumentors: Optional[List[str]] = None,
        firewall_base_url: Optional[str] = None,
        enable_firewall_instrumentation: Optional[bool] = False,
    ):
        """Initialize the Layer SDK with the required configuration.

        Args:
            base_url (str, optional): The base URL for the Layer API.
                Defaults to the `LAYER_BASE_URL` environment variable.
            application_id (str, optional): The application ID.
                Defaults to the `LAYER_APPLICATION_ID` environment variable.
            environment (str, optional): The environment.
                Defaults to the `LAYER_ENVIRONMENT` environment variable.
            auth_provider (AuthProvider, optional): The authentication provider. Defaults to None.
            http_session (requests.Session, optional): The HTTP session/client.
                Defaults to preconfigured HTTP client with retry and pool.
            http_timeout (int, optional): The HTTP timeout.
                Defaults to `LAYER_HTTP_TIMEOUT` environment variable or 10 seconds
            platform (Platform, optional): The platform. Defaults to None.
            disabled_instrumentors (List[str], optional): The list of disabled instrumentors.
                Defaults to None i.e. enabling all.
            firewall_base_url (str, optional): The base URL for the firewall API.
            enable_firewall_instrumentation (bool, optional): Enable firewall instrumentation.
                It will automatically call firewall API for each session action creation.

        Raises:
            LayerMissingRequiredConfigurationError: If the required configuration is missing.
            LayerAlreadyInitializedError: If the SDK is already initialized.
        """
        if self._initialized:
            logger.error("Layer SDK already initialized")

            return

        base_url = base_url or os.environ.get("LAYER_BASE_URL")
        if not base_url:
            raise LayerMissingRequiredConfigurationError("Missing required argument `base_url`")

        self._base_url = base_url.strip().strip('"').strip("'").rstrip("/")

        if not platform:
            platform = get_platform()
        self._platform = platform

        environment = environment or os.environ.get("LAYER_ENVIRONMENT")
        if environment:
            environment = environment.lower()
        self._environment = environment

        application_id = application_id or os.environ.get("LAYER_APPLICATION_ID")
        if not application_id:
            raise LayerMissingRequiredConfigurationError("Application ID must be provided")
        self._application_id = application_id

        firewall_base_url = firewall_base_url or os.environ.get("LAYER_FIREWALL_BASE_URL")
        self._firewall_base_url = firewall_base_url

        self._auth_provider = auth_provider

        if not http_session:
            http_session = _create_default_http_session()
        self._http_session = http_session

        self._http_timeout = http_timeout or int(os.environ.get("LAYER_HTTP_TIMEOUT", 10))
        self._enable_firewall_instrumentation = enable_firewall_instrumentation or False
        if self._enable_firewall_instrumentation and not self._firewall_base_url:
            raise LayerMissingRequiredConfigurationError("Firewall base URL must be provided "
                                                         "if firewall instrumentation is enabled")

        self._disabled_instrumentors = disabled_instrumentors if disabled_instrumentors else []
        self._instrument()

        self._initialized = True
        logger.debug(
            f"Layer SDK initialized with base_url={self._base_url}, "
            f"application_id={self._application_id}, "
            f"environment={self._environment}, "
            f"firewall_base_url={self._firewall_base_url}"
        )

    def _instrument(self):
        """Instruments the SDK with the available instrumentors."""
        for name, instrumentor_class in instrumentor_instances.items():
            if name in self._disabled_instrumentors:
                logger.debug(f"Instrumentor {name} is disabled")

                continue

            instrumentor_instance = instrumentor_class(self)
            if not instrumentor_instance.supports():
                logger.warning(f"Instrumentor {name} is not supported")

                continue

            try:
                instrumentor_instance.instrument()
            except Exception as e:
                logger.error("Failed to instrument %s: %s", name, e)

                continue

            logger.debug(f"Instrumentor {name} is enabled")

    def _get_headers(self) -> Dict[str, str]:
        """Get the headers for the HTTP request.

        Returns:
            Dict[str, str]: The headers for the HTTP request
        """
        headers = {}
        if self._auth_provider:
            headers = self._auth_provider.get_headers()

        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        headers["User-Agent"] = f"layer-sdk-python/{__version__}"

        return headers

    def _encode_request(self, request: Any) -> bytes:
        try:
            body = orjson.dumps(
                request,
                option=orjson.OPT_UTC_Z
                | orjson.OPT_NAIVE_UTC
                | orjson.OPT_OMIT_MICROSECONDS
                | orjson.OPT_SERIALIZE_UUID
                | orjson.OPT_SERIALIZE_DATACLASS,
            )
        except TypeError as e:
            logger.warning(f"Failed to serialize request: {e}. Falling back to json.")

            try:
                body = json.dumps(
                    request,
                    ensure_ascii=True,
                ).encode("utf-8")
            except Exception as e:
                raise LayerRequestPreparationError(f"Failed to serialize request: {e}")

        return body

    def create_session(self, **kwargs) -> str:
        """Create a new session.

        Args:
            **kwargs: The session attributes. See `SessionRequest` for more information.

        Raises:
            LayerHTTPError: If the HTTP request fails.
            LayerRequestPreparationError: If the request preparation fails.

        Returns:
            str: The session ID
        """
        url = f"{self._base_url}/v1/sessions"

        try:
            request = SessionRequest(
                application_id=self._application_id,
                **kwargs,
            )
        except TypeError as e:
            raise LayerRequestPreparationError(str(e))

        if self._environment:
            request.attributes["environment"] = self._environment

        request.attributes = {
            **request.attributes,
            **platform_session_attributes(__version__, platform=self._platform),
        }

        try:
            response = self._http_session.post(
                url,
                data=self._encode_request(request),
                headers=self._get_headers(),
                timeout=self._http_timeout,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed request to create session: {e}")
            raise LayerRequestError(f"Failed request to create session: {e}")

        if response.status_code > 299 or response.status_code < 200:
            logger.error(
                f"Failed to create session: "
                f"{response.status_code} {response.content.decode('utf-8')}"
            )

            raise LayerHTTPError(
                "Failed to create session",
                response.status_code,
                response.content.decode("utf-8"),
            )

        session_id = orjson.loads(response.content)["session_id"]
        logger.debug(f"Session created with ID: {session_id}")

        return session_id

    def append_action(self, session_id: Union[str, uuid.UUID], **kwargs) -> None:
        """Append an action to a session.

        Args:
            session_id (Union[str, uuid.UUID]): The session ID
            **kwargs: The action attributes. See `SessionActionRequest` for more information.

        Raises:
            LayerRequestPreparationError: If the request preparation fails.
            LayerHTTPError: If the HTTP request fails.
            LayerFirewallSessionBlocked: If the firewall recommends to block the session.
                Only raised if `enable_firewall_instrumentation` is set to True.
        """
        if self._enable_firewall_instrumentation:
            try:
                firewall_lookup_response = self.firewall_session_lookup(session_id)

                if firewall_lookup_response.decision == FirewallLookupDecision.BLOCK:
                    raise LayerFirewallSessionBlocked(f"Session '{session_id}' is "
                                                      f"blocked by the firewall")

                logger.info(f"Session '{session_id}' was evaluated by the firewall. "
                            f"Decision: {firewall_lookup_response.decision}")
            except LayerFirewallException as e:
                logger.error(f"Failed to lookup session '{session_id}' in firewall: {e}. "
                             f"Skipping firewall check")

        url = f"{self._base_url}/v1/sessions/{str(session_id)}/actions"

        try:
            request = SessionActionRequest(**kwargs)
        except TypeError as e:
            raise LayerRequestPreparationError(str(e))

        try:
            response = self._http_session.post(
                url,
                data=self._encode_request(request),
                headers=self._get_headers(),
                timeout=self._http_timeout,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed request to append session action: {e}")
            raise LayerRequestError(f"Failed request to append session action: {e}")

        if response.status_code != 202:
            logger.error(
                f"Failed to append session action: "
                f"{response.status_code} {response.content.decode('utf-8')}"
            )
            raise LayerHTTPError(
                "Failed to append session action",
                response.status_code,
                response.content.decode("utf-8"),
            )

        logger.debug(f"Session action appended to session {session_id}")

    def firewall_session_lookup(
        self,
        session_id: Union[str, uuid.UUID]
    ) -> FirewallSessionLookupResponse:
        """Lookup a session in the firewall.

        Args:
            session_id (Union[str, uuid.UUID]): The session ID

        Raises:
            LayerFirewallRequestError: If the request to the firewall fails.
            LayerFirewallHTTPError: If the firewall returns an HTTP error.
            LayerMissingRequiredConfigurationError: If the firewall base URL is not provided.

        """
        if not self._firewall_base_url:
            raise LayerMissingRequiredConfigurationError("Firewall base URL must be provided")

        url = f"{self._firewall_base_url}/v1/sessions/{session_id}"

        try:
            response = self._http_session.get(
                url,
                headers=self._get_headers(),
                timeout=self._http_timeout,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed request to the firewall session lookup: {e}")
            raise LayerFirewallRequestError(f"Failed request to the firewall session lookup: {e}")

        if response.status_code != 200:
            logger.error(
                f"Failed firewall session lookup: "
                f"{response.status_code} {response.content.decode('utf-8')}"
            )
            raise LayerFirewallHTTPError(
                "Failed firewall session lookup",
                response.status_code,
                response.content.decode("utf-8"),
            )

        return FirewallSessionLookupResponse(**orjson.loads(response.content))

    def session(
        self,
        *,
        session_id: Optional[Union[str, uuid.UUID]] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Decorate to create a new session for a function.

        Args:
            session_id (Union[str, uuid.UUID], optional):
                Optional custom session ID if needs to be enforced.
            attributes (Dict[str, Any], optional): The session attributes.
                See `SessionRequest` for more information.

        Returns:
            Callable: The decorator
        """

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                new_session_id = self.create_session(attributes=attributes, session_id=session_id)

                sig = inspect.signature(func)
                if 'session_id' in sig.parameters:
                    kwargs['session_id'] = new_session_id

                result = func(*args, **kwargs)

                return result

            return wrapper

        return decorator

    def action(
        self,
        *,
        session_id: Union[str, uuid.UUID],
        kind: SessionActionKind,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Decorate to append an action to a session for a function.

        The wrapped function must return the tuple `(data, error, scanners)`.
        The `data` is the result of the action, the `error` is the error if any,
        and the `scanners` are the scanners if any.

        Args:
            session_id (Union[str, uuid.UUID]): The session ID
            kind (SessionActionKind): The action kind
            attributes (Dict, optional): The action attributes (see `SessionActionRequest`).

        Returns:
            Callable: The decorator
        """

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = datetime.now(timezone.utc)
                result = func(*args, **kwargs)
                end_time = datetime.now(timezone.utc)

                data, error, scanners = result, None, None
                if isinstance(result, tuple):
                    data, error, scanners = result + (None,) * (3 - len(result))

                self.append_action(
                    session_id=session_id,
                    kind=kind,
                    start_time=start_time,
                    end_time=end_time,
                    attributes=attributes or None,
                    data=data,
                    error=error,
                    scanners=scanners,
                )

                return result

            return wrapper

        return decorator
