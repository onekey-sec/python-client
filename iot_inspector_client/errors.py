"""Define error messages."""

import json
from typing import Optional


class ClientError(Exception):
    """Base class for all Client errors."""

    def __init__(self, message: Optional[str] = None):
        """Super message."""
        super().__init__(message or self.MESSAGE)


class NotLoggedIn(ClientError):
    """Not logged in error."""

    MESSAGE = (
        "You are not logged in yet. \n"
        "You have to call client.login(email, password) first."
    )


class TenantNotSelected(ClientError):
    """Tenant not selected error."""

    MESSAGE = (
        "You have to select a Tenant (Environment) "
        "with client.use_tenant(tenant) first."
    )


class InvalidCABundle(ClientError):
    """Invalid CA Bundle."""

    MESSAGE = "The CA bundle is invalid or doesn't exist."


class QueryError(ClientError):
    """raised when a GraphQL query returns errors."""

    def __init__(self, errors_json: dict):
        """Initialize query errors."""
        self._errors = errors_json

    def __str__(self):
        """Return errors as json dump."""
        return json.dumps(self._errors, indent=4)


class WSSDisabledSubcribeNotPossible(ClientError):
    """WSS disabled but needed for subscription error."""

    MESSAGE = (
        "WSS is disabled. For using subscriptions "
        "WSS needs to be enabled."
    )
