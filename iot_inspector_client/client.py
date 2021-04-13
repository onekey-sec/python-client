import gc
import secrets
from pathlib import Path
from typing import Optional, List, Dict

try:
    from importlib import resources
except ImportError:
    import importlib_resources as resources

import httpx
from pydantic import parse_obj_as
from authlib.oidc.core import IDToken
from authlib.jose import jwt
from .queries import load_query
from . import errors
from . import models as m
from . import keys


CLIENT_ID = "IoT Inspector Python SDK"
TOKEN_NAMESPACE = "https://www.iot-inspector.com/"

IOT_INSPECTOR_KEYS = {
    "demo.iot-inspector.com": {
        "id_token_public_key": "demo_id_token_public_key.pem",
        "tenant_token_public_key": "demo_tenant_token_public_key.pem",
        "ca_path": "ca.pem",
    },
    "*.iot-inspector.com": {
        "id_token_public_key": "platform_id_token_public_key.pem",
        "tenant_token_public_key": "platform_tenant_token_public_key.pem",
        "ca_path": "ca.pem",
    },
}


class Client:
    def __init__(
        self,
        api_url: str,
        id_token_public_key: Optional[Path] = None,
        tenant_token_public_key: Optional[Path] = None,
        ca_bundle: Optional[Path] = None,
    ):
        self._id_token_public_key = self._load_key(
            api_url, "id_token_public_key", id_token_public_key
        )

        self._tenant_token_public_key = self._load_key(
            api_url, "tenant_token_public_key", tenant_token_public_key
        )

        self._client = self._setup_httpx_client(api_url, ca_bundle)
        self._state = _LoginState()

    def _setup_httpx_client(self, api_url: str, ca_bundle: Optional[Path] = None):
        if ca_bundle is not None:
            ca = ca_bundle.expanduser()
            if not ca.exists():
                raise errors.InvalidCABundle

            return httpx.Client(base_url=api_url, verify=str(ca))
        else:
            resource_name = self._get_resource_name(api_url, "ca_path")
            with resources.path(keys, resource_name) as ca:
                return httpx.Client(base_url=api_url, verify=str(ca))

    def _load_key(self, api_url: str, key_name: str, path: Optional[Path] = None):
        if path is not None:
            return path.read_bytes()
        else:
            resource_name = self._get_resource_name(api_url, key_name)
            return resources.read_binary(keys, resource_name)

    @staticmethod
    def _get_resource_name(api_url: str, key_name: str):
        domain = httpx.URL(api_url).host
        try:
            return IOT_INSPECTOR_KEYS[domain][key_name]
        except KeyError:
            # We try to match on a wildcard domain as it is used for *.iot-inspector.com domain
            domain_base = domain.split(".", maxsplit=1)[-1]
            wildcard_domain = f"*.{domain_base}"
            return IOT_INSPECTOR_KEYS.get(wildcard_domain, {}).get(key_name)

    def login(self, email: str, password: str):
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
        tenants = id_token[TOKEN_NAMESPACE + "tenants"]
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
            raise errors.TenantNotSelected

        return self._post(path, headers, **kwargs)

    def get_tenant(self, name: str):
        """Get Tenant by name. Raises KeyError if not found."""
        try:
            return self._state.tenants[name]
        # in case of None[name]
        except TypeError:
            raise errors.NotLoggedIn

    def get_all_tenants(self) -> List[m.Tenant]:
        """Get the list of Tenants you have access to."""
        try:
            return list(self._state.tenants.values())
        # in case of None.tenants
        except AttributeError:
            raise errors.NotLoggedIn

    def use_tenant(self, tenant: m.Tenant):
        """Select the Environment (Tenant) you want to work with."""
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
        self._state.raw_tenant_token = json_res["tenant_token"]

    def query(self, query: str, variables: Optional[Dict] = None):
        """Issues a GraphQL query and returns the results"""
        res = self._post_with_token(
            "/graphql", json={"query": query, "variables": variables}
        )

        if "errors" in res:
            raise errors.QueryError(res["errors"])

        return res["data"]

    def upload_firmware(
        self, metadata: m.FirmwareMetadata, path: Path, *, enable_monitoring: bool
    ):
        variables = {
            "firmware": {
                "name": metadata.name,
                "version": metadata.version,
                "releaseDate": metadata.release_date,
                "notes": metadata.notes,
                "enableMonitoring": enable_monitoring,
            },
            "vendorName": metadata.vendor_name,
            "productName": metadata.product_name,
            "productCategory": metadata.product_category,
            "productGroupID": str(metadata.product_group_id),
        }

        upload_mutation = load_query("create_firmware_upload.graphql")
        res = self.query(upload_mutation, variables=variables)

        if "errors" in res["createFirmwareUpload"]:
            raise errors.QueryError(res["createFirmwareUpload"]["errors"])

        upload_url = res["createFirmwareUpload"]["uploadUrl"]
        res = self._post_with_token(upload_url, files={"firmware": path.open("rb")})
        return res

    def logout(self):
        del self._state
        gc.collect()
        self._state = _LoginState()


def _verify_token(
    nonce: str, email, raw_token: str, public_key: bytes, claims_cls=None
):
    """Verify a JWT token signature with the public_key."""
    claims_options = {
        "iss": {"essential": True, "value": TOKEN_NAMESPACE},
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
