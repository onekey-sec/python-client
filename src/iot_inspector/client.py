import gc
import secrets
from pathlib import Path
from typing import Optional, List, Dict
import httpx
from pydantic import parse_obj_as
from authlib.oidc.core import IDToken
from authlib.jose import jwt
from . import errors
from . import models as m


CLIENT_ID = "IoT Inspector Python SDK"
BASE_URL = "https://app.iot-inspector.com/"
API_URL = BASE_URL + "api"


class Client:
    def __init__(
        self,
        api_url: str = API_URL,
        id_token_public_key: Optional[Path] = None,
        tenant_token_public_key: Optional[Path] = None,
        ca_bundle: Optional[Path] = None,
    ):
        self._id_token_public_key = id_token_public_key.read_bytes()
        self._tenant_token_public_key = tenant_token_public_key.read_bytes()
        ca_bundle = ca_bundle.expanduser()
        if not ca_bundle.exists():
            raise errors.InvalidCABundle
        self._client = httpx.Client(base_url=api_url, verify=str(ca_bundle))
        self._state = _LoginState()

    def authorize(self, email: str, password: str):
        nonce = secrets.token_urlsafe()
        payload = {
            "email": email,
            "password": password,
            "client_id": CLIENT_ID,
            "nonce": nonce,
        }
        json_res = self._post("/authorize", json=payload)
        id_token = _verify_token(
            nonce,
            email,
            raw_token=json_res["id_token"],
            public_key=self._id_token_public_key,
            claims_cls=IDToken,
        )
        tenants = id_token[BASE_URL + "tenants"]
        tenants = parse_obj_as(List[m.Tenant], tenants)
        self._state.tenants = {e.name: e for e in tenants}
        self._state.email = email
        self._state.raw_id_token = json_res["id_token"]

    def _post(self, path: str, headers: Optional[Dict] = None, **kwargs):
        response = self._client.post(path, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def _post_with_token(self, path: str, **kwargs):
        try:
            headers = {"Authorization": "Bearer " + self._state.raw_tenant_token}
        # in case of None + str
        except TypeError:
            raise errors.NotLoggedIn

        return self._post(path, headers, **kwargs)

    def get_tenant(self, name: str):
        """Get Tenant by name. Raises KeyError if not found."""
        try:
            return self._state.tenants[name]
        # in case of None[name]
        except TypeError:
            raise errors.NotAuthorized

    def get_all_tenants(self) -> List[m.Tenant]:
        """Get the list of Tenants you have access to."""
        try:
            return list(self._state.tenants.values())
        # in case of None.tenants
        except AttributeError:
            raise errors.NotAuthorized

    def login(self, tenant: m.Tenant):
        """Login to the selected Environment (Tenant)."""
        if not self._state.is_authorized:
            raise errors.NotAuthorized

        nonce = secrets.token_urlsafe()
        payload = {
            "id_token": self._state.raw_id_token,
            "client_id": CLIENT_ID,
            "tenant_id": str(tenant.id),
            "nonce": nonce,
        }
        json_res = self._post("/token", json=payload)
        _verify_token(
            nonce,
            self._state.email,
            json_res["tenant_token"],
            self._tenant_token_public_key,
        )
        # TODO: We don't want to store the id_token for long,
        # but what's the best strategy here?
        del self._state.raw_id_token
        del self._state.email
        # force deleting unreferenced variables
        gc.collect()
        self._state.raw_id_token = None
        self._state.raw_tenant_token = json_res["tenant_token"]

    @property
    def is_authorized(self):
        return self._state.is_authorized

    @property
    def is_logged_in(self):
        return self._state.is_logged_in

    def query(self, query: str):
        """Issues a GraphQL query and returns the results"""
        res = self._post_with_token("/graphql", {"query": query})
        return res["data"]

    def logout(self):
        del self._state
        gc.collect()
        self._state = _LoginState()


def _verify_token(
    nonce: str, email, raw_token: str, public_key: bytes, claims_cls=None
):
    """Verify a JWT token signature with the public_key."""
    claims_options = {
        "iss": {"essential": True, "value": BASE_URL},
        "aud": {"essential": True, "value": CLIENT_ID},
        "sub": {"essential": True, "value": email},
    }
    decoded_token = jwt.decode(
        raw_token,
        public_key,
        claims_cls=claims_cls,
        claims_options=claims_options,
        claims_params={"nonce": nonce},
    )
    decoded_token.validate()
    return decoded_token


class _LoginState:
    """Keeps state after login.
    Client.logout() will simply delete the instance from memory.
    """

    def __init__(self):
        self.email = None
        self.tenants = None
        self.raw_id_token = None
        self.raw_tenant_token = None

    @property
    def is_authorized(self):
        return self.raw_id_token is not None

    @property
    def is_logged_in(self):
        return self.raw_tenant_token is not None
