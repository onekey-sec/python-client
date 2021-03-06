from typing import Optional


class ClientError(Exception):
    """Base class for all Client errors."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(message or self.MESSAGE)


class NotAuthorized(ClientError):
    MESSAGE = (
        "You are not authorized yet. \n"
        "You have to call client.authorize(email, password) first."
    )


class NotLoggedIn(ClientError):
    MESSAGE = "You have to login first."


class InvalidCABundle(ClientError):
    MESSAGE = "The CA bundle is invalid or doesn't exist."
