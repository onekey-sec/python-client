# ONEKEY API Client

This is the official Python client for the
[ONEKEY](https://www.onekey.com/) public API. This package provides both a cli and a python library.

# Installation

The client is available at https://github.com/onekey-sec/python-client or can be installed as a python package:

```commandline
pip install onekey-client
```

# CLI Usage

The client can be used with the onekey command and offers multiple subcommands:

```commandline
Usage: onekey [OPTIONS] COMMAND [ARGS]...

Options:
  --api-url TEXT        ONEKEY platform API endpoint  [default:
                        https://app.eu.onekey.com/api]
  --disable-tls-verify  Disable verifying server certificate, use only for
                        testing
  --email TEXT          Email to authenticate on the ONEKEY platform
  --password TEXT       Password to authenticate on the ONEKEY platform
  --tenant TEXT         Tenant name on ONEKEY platform
  --token TEXT          API token to authenticate on the ONEKEY platform
  --help                Show this message and exit.

Commands:
  ci-result         Fetch analysis results for CI
  get-tenant-token  Get tenant specific Bearer token
  list-tenants      List available tenants
  upload-firmware   Uploads a firmware to the ONEKEY platform
```

To use the ONEKEY platform a valid email & password need to be supplied along with specifying the tenant name to be
used. (SSO authentication is currently not supported.) Preferred alternative is to use a dedicated API token based
authentication, API tokens can be generated on the ONEKEY platform.

The required parameters can be supplied through command line arguments or using environment variables prefixed with
`ONEKEY_`, such as the following two are identical:

```commandline
onekey --email "<email>" --tenant "<tenant-name>" --password "<password>" get-tenant-token
```

```commandline
ONEKEY_EMAIL="<email>" ONEKEY_TENANT_NAME="<tenant-name>" ONEKEY_PASSWORD="<password>" onekey get-tenant-token
```

Environment variables and command line arguments can be also mixed. Using environment variables is useful when the
client is used from CI/CD jobs/tasks.

# API Usage

First, you have to log in and select a tenant:

```python
from onekey_client import Client

YOUR_API_URL = "https://app.eu.onekey.com/api"

client = Client(api_url=YOUR_API_URL)

client.login(EMAIL, PASSWORD)
tenant = client.get_tenant("Environment name")
client.use_tenant(tenant)
```

Or use an API Token:

```python
from onekey_client import Client

YOUR_API_URL = "https://app.eu.onekey.com/api"

client = Client(api_url=YOUR_API_URL)

client.use_token(API_TOKEN)
```


After you logged in and selected the tenant, you can query the GraphQL API

```python
GET_ALL_FIRMWARES = """
query {
  allFirmwares {
    id
    name
  }
}
"""
res = client.query(GET_ALL_FIRMWARES)
print(res)

GET_PRODUCT_GROUPS = """
query {
  allProductGroups {
    id
    name
  }
}
"""
res = client.query(GET_PRODUCT_GROUPS)
default_product_group = next(pg for pg in res["allProductGroups"] if pg["name"] == "Default")

GET_ANALYSIS_CONFIGURATIONS = """
query {
  allAnalysisConfigurations {
    id
    name
  }
}
"""
res = client.query(GET_ANALYSIS_CONFIGURATIONS)
default_analysis_configuration = next(conf for conf in res["allAnalysisConfigurations"] if conf["name"] == "Default")
```

You can upload firmwares:

```python
metadata = FirmwareMetadata(
    name="myFirmware",
    vendor_name="myVendor",
    product_name="myProduct",
    product_group_id=default_product_group["id"],
    analysis_configuration_id=default_analysis_configuration["id"],
)

firmware_path = Path("/path/to/firmware.bin")
res = client.upload_firmware(metadata, firmware_path, enable_monitoring=True)
print(res)
```

# Support

You can create a [new issue in this repo](https://github.com/onekey-sec/python-client/issues/new)
or contact us at support@onekey.com.
