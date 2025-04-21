import requests
from requests.adapters import Retry, HTTPAdapter


def _create_default_http_session() -> requests.Session:
    """Create a default http client based on the requests with retry and timeout settings.

    We chose these settings to make sure
    that the client is robust and can handle most of the common cases.

    Returns:
        requests.Session: A session object with the default settings.
    """
    retry_strategy = Retry(
        total=3,
        status_forcelist=[502, 503, 504, 408, 425],
        backoff_factor=0.5,
        allowed_methods=None,
        raise_on_redirect=False,
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=3,
        pool_maxsize=10,
        pool_block=False,
    )
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session
