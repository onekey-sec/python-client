# IoT Inspector API Client

This is the official Python client for the
[IoT Inspector](https://www.iot-inspector.com/) public API.

# Usage

First, you have to log in and select a tenant:

```python
from iot_inspector_client import Client

YOUR_API_URL = "https://demo.iot-inspector.com/api"

client = Client(api_url=YOUR_API_URL)

client.login(EMAIL, PASSWORD)
tenant = client.get_tenant("Environment name")
client.use_tenant(tenant)
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
```

You can upload firmwares:

```python
metadata = FirmwareMetadata(
    name="myFirmware",
    vendor_name="myVendor",
    product_name="myProduct",
    product_group_id=default_product_group["id"],
)

firmware_path = Path("/path/to/firmware.bin")
res = client.upload_firmware(metadata, firmware_path, enable_monitoring=True)
print(res)
```

# Support

You can create a [new issue in this repo](https://github.com/IoT-Inspector/python-client/issues/new)
or contact us at support@iot-inspector.com.
