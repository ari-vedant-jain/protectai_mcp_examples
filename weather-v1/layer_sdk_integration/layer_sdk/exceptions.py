"""Exceptions for the Layer SDK."""

from __future__ import annotations


class LayerSDKException(Exception):
    """Base class for exceptions in this module."""


class LayerRequestError(LayerSDKException):
    """Exception raised for errors in the request."""


class LayerHTTPError(LayerSDKException):
    """Exception raised for errors in the HTTP request."""

    def __init__(self, message: str, status_code: int, response_data: str):
        """Initialize the exception.

        Args:
            message (str): The error message
            status_code (int): The HTTP status code
            response_data (str): The response data
        """
        self.status_code = status_code
        self.message = message
        self.response_data = response_data

        super().__init__(f"HTTP Error {self.status_code}: {self.message}\n{self.response_data}")


class LayerAuthError(LayerSDKException):
    """Exception raised when authentication fails."""


class LayerRequestPreparationError(LayerSDKException):
    """Exception raised when a request fails."""


class LayerMissingRequiredConfigurationError(LayerSDKException):
    """Exception raised when a required configuration is missing."""


class LayerSchemaValidationError(LayerSDKException):
    """Exception raised when a schema validation fails."""


class LayerFirewallException(LayerSDKException):
    """Exception raised for errors in the firewall."""


class LayerFirewallRequestError(LayerFirewallException):
    """Exception raised for errors in the request to the firewall."""


class LayerFirewallHTTPError(LayerHTTPError, LayerFirewallException):
    """Exception raised when a firewall returns an HTTP error."""


class LayerFirewallSessionBlocked(LayerSDKException):
    """Exception raised when a firewall recommends to block the session."""
