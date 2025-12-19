import functools
import gc
import secrets
from pathlib import Path

try:
    from importlib import resources
except ImportError:
    import importlib_resources as resources

import httpx
from authlib.jose import jwt
from authlib.oidc.core import IDToken
from httpx import URL
from pydantic import parse_obj_as

from . import errors, keys
from . import models as m
from .queries import load_query

CLIENT_ID = "ONEKEY Python SDK"
TOKEN_NAMESPACE = "https://www.onekey.com/"


def _login_required(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._state.tenants:
            raise errors.NotLoggedIn

        return func(self, *args, **kwargs)

    return wrapper


def _tenant_required(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._state.raw_tenant_token is None:
            raise errors.TenantNotSelected

        return func(self, *args, **kwargs)

    return wrapper


class Client:
    def __init__(
        self,
        api_url: str,
        ca_bundle: Path | None = None,
        disable_tls_verify: bool | None = False,
    ):
        self._api_url = URL(api_url)
        self._client = self._setup_httpx_client(api_url, ca_bundle, disable_tls_verify)

        self._id_token_public_key = self._load_key("id-token-public-key")

        self._tenant_token_public_key = self._load_key("tenant-token-public-key")

        self._state = _LoginState()

    def _setup_httpx_client(
        self,
        api_url: str,
        ca_bundle: Path | None = None,
        disable_tls_verify: bool | None = False,
    ):
        if disable_tls_verify:
            return httpx.Client(base_url=api_url, verify=False)

        if ca_bundle is not None:
            ca = ca_bundle.expanduser()
            if not ca.exists():
                raise errors.InvalidCABundle

            return httpx.Client(base_url=api_url, verify=str(ca))
        with resources.path(keys, "ca.pem") as ca:
            return httpx.Client(base_url=api_url, verify=str(ca))

    def _load_key(self, key_name: str, path: Path | None = None):
        if path is not None:
            return path.read_bytes()
        response = self._client.get(f"/{key_name}.pem")
        response.raise_for_status()
        return response.read()

    @property
    def api_url(self) -> URL:
        return self._api_url

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
        tenants = parse_obj_as(list[m.Tenant], tenants)
        self._state.tenants = {e.name: e for e in tenants}
        self._state.email = email
        self._state.raw_id_token = json_res["id_token"]

    def use_token(self, token: str):
        try:
            tenant_id, _ = token.split("/", 1)
        except ValueError:
            raise errors.InvalidAPIToken()

        self._state.raw_tenant_token = token

        self_query = load_query("get_self.graphql")
        response = self.query(self_query)
        self._state.email = response["user"]["email"]
        tenant = m.Tenant(id=tenant_id, name=response["tenant"]["name"])
        self._state.tenants = {tenant.name: tenant}
        self._state.tenant = tenant

    def _post(self, path: str, headers: dict | None = None, **kwargs):
        response = self._client.post(path, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    @_tenant_required
    def _post_with_token(self, path: str, **kwargs):
        headers = self.get_auth_headers()

        return self._post(path, headers, **kwargs)

    @_tenant_required
    def get_auth_headers(self):
        return {"Authorization": "Bearer " + self._state.raw_tenant_token}

    @_login_required
    def get_tenant(self, name: str):
        """Get Tenant by name. Raises KeyError if not found."""
        return self._state.tenants[name]

    @_login_required
    def get_all_tenants(self) -> list[m.Tenant]:
        """Get the list of Tenants you have access to."""
        return list(self._state.tenants.values())

    @_login_required
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
        self._state.tenant = tenant

    @_tenant_required
    def refresh_tenant_token(self):
        if self._state.raw_id_token is not None:
            self.use_tenant(self._state.tenant)

    @_tenant_required
    def query(self, query: str, variables: dict | None = None, timeout=60):
        """Issues a GraphQL query and returns the results"""
        res = self._post_with_token(
            "/graphql", json={"query": query, "variables": variables}, timeout=timeout
        )

        if "errors" in res:
            raise errors.QueryError(res["errors"])

        return res["data"]

    @_tenant_required
    def upload_firmware(
        self,
        metadata: m.FirmwareMetadata,
        path: Path,
        *,
        enable_monitoring: bool,
        timeout=60,
    ):
        variables = {
            "firmware": {
                "name": metadata.name,
                "version": metadata.version,
                "releaseDate": metadata.release_date,
                "notes": metadata.notes,
                "enableMonitoring": enable_monitoring,
                "analysisConfigurationId": str(metadata.analysis_configuration_id),
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
        res = self._post_with_token(
            upload_url, files={"firmware": path.open("rb")}, timeout=timeout
        )
        return res

    @_tenant_required
    def get_product_groups(self):
        product_groups_query = load_query("get_product_groups.graphql")
        response = self.query(product_groups_query)
        return {pg["name"]: pg["id"] for pg in response["allProductGroups"]}

    @_tenant_required
    def get_analysis_configurations(self):
        analysis_configurations_query = load_query(
            "get_analysis_configurations.graphql"
        )
        response = self.query(analysis_configurations_query)
        return {c["name"]: c["id"] for c in response["allAnalysisConfigurations"]}

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
        self.tenant = None
