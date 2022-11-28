import sys

from getpass import getpass
from pathlib import Path

from onekey_client import Client
from onekey_client.models import FirmwareMetadata

API_URL = "https://app.eu.onekey.com/api"
EMAIL = sys.argv[1]
PASSWORD = getpass()

print("Login to ONEKEY", EMAIL, "@", API_URL)
client = Client(API_URL)
client.login(EMAIL, PASSWORD)

tenants = client.get_all_tenants()
# Pick the first one
tenant = tenants[0]
print("Using tenant:", tenant.name)
client.use_tenant(tenant)

GET_ALL_PRODUCT_GROUP_IDS = """
{
  allProductGroups {
    id
    name
  }
}
"""

response = client.query(GET_ALL_PRODUCT_GROUP_IDS)
product_group_ids = [pg["id"] for pg in response["allProductGroups"]]


metadata = FirmwareMetadata(
    name="myFirmware",
    vendor_name="myVendor",
    product_name="myProduct",
    product_group_id=product_group_ids[0],
)

firmware_path = Path(sys.argv[2])
res = client.upload_firmware(metadata, firmware_path, enable_monitoring=True)
print(res)
