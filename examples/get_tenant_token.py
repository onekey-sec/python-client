import json
import sys
from getpass import getpass
from onekey_client import Client

API_URL = "https://demo.onekey.com/api"
EMAIL = sys.argv[1]
PASSWORD = getpass()


print("Login to ONEKEY", EMAIL, "@", API_URL)
client = Client(API_URL)
client.login(EMAIL, PASSWORD)
tenants = client.get_all_tenants()

print("Tenants:", ", ".join([tenant.name for tenant in tenants]))

if len(sys.argv) > 2:
    # Filter tenants that matches the provided pattern
    tenants = filter(lambda tenant: sys.argv[2] in tenant.name, tenants)

# Pick the first one
tenant = tenants[0]

print("Using tenant:", tenant.name)
client.use_tenant(tenant)

print(json.dumps(client.get_auth_headers()))
