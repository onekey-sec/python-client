import json
from typing import Optional


class ClientError(Exception):
    """Base class for all Client errors."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(message or self.MESSAGE)


class NotLoggedIn(ClientError):
    MESSAGE = (
        "You are not logged in yet. \n"
        "You have to call client.login(email, password) first."
    )


class TenantNotSelected(ClientError):
    MESSAGE = "You have to select a Tenant (Environment) with client.use_tenant(tenant) first."


class InvalidCABundle(ClientError):
    MESSAGE = "The CA bundle is invalid or doesn't exist."


class QueryError(ClientError):
    """raised when a GraphQL query returns errors."""

    def __init__(self, errors_json: dict):
        self._errors = errors_json

    def __str__(self):
        return json.dumps(self._errors, indent=4)
