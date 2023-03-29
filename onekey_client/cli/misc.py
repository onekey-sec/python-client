import json

import click

from onekey_client import Client


@click.command()
@click.pass_obj
def list_tenants(client: Client):
    """List available tenants"""

    tenants = client.get_all_tenants()
    for tenant in tenants:
        click.echo(f"{tenant.name} ({tenant.id}")


@click.command()
@click.pass_obj
def get_tenant_token(client: Client):
    """Get tenant specific Bearer token"""

    click.echo(json.dumps(client.get_auth_headers()))
