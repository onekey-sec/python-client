import sys

import click
import httpx

from onekey_client import Client

from .ci import ci_result
from .firmware_upload import upload_firmware
from .misc import get_tenant_token, list_tenants


@click.group()
@click.option(
    "--api-url",
    default="https://app.eu.onekey.com/api",
    show_default=True,
    help="ONEKEY platform API endpoint",
)
@click.option(
    "--disable-tls-verify",
    default=False,
    show_default=True,
    help="Disable verifying server certificate, use only for testing",
    is_flag=True,
)
@click.option("--email", help="Email to authenticate on the ONEKEY platform")
@click.option(
    "--password",
    hide_input=True,
    help="Password to authenticate on the ONEKEY platform",
)
@click.option("--tenant", "tenant_name", help="Tenant name on ONEKEY platform")
@click.option("--token", help="API token to authenticate on the ONEKEY platform")
@click.pass_context
def cli(ctx, api_url, disable_tls_verify, email, password, tenant_name, token):
    client = Client(api_url=api_url, disable_tls_verify=disable_tls_verify)
    if token is not None and (
        email is not None or password is not None or tenant_name is not None
    ):
        click.echo(
            "Invalid authentication details, either specify token or email/password/tenant, but not both!"
        )
        sys.exit(1)

    if token is None and (email is None or password is None or tenant_name is None):
        click.echo(
            "Invalid authentication details, specify email, password and tenant, if token is not specified!"
        )
        sys.exit(1)

    if token is not None:
        login_with_token(client, token, api_url)
    else:
        login_with_email(client, email, password, tenant_name, api_url)
    ctx.obj = client


def login_with_email(client, email, password, tenant_name, api_url):
    try:
        client.login(email, password)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == httpx.codes.UNAUTHORIZED:
            click.echo(f"Authentication failed on {email} @ {api_url}")
            sys.exit(1)
        else:
            click.echo(
                f"Error connecting to ONEKEY platform: '{api_url}', error: {e.response.status_code}"
            )
            sys.exit(2)

    try:
        tenant = client.get_tenant(tenant_name)
    except KeyError:
        click.echo(f"Invalid tenant: {tenant_name}")
        tenants = client.get_all_tenants()
        click.echo("Available tenants:")
        for tenant in tenants:
            click.echo(f"- {tenant.name} ({tenant.id}")
        sys.exit(3)

    client.use_tenant(tenant)


def login_with_token(client, token, api_url):
    try:
        client.use_token(token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == httpx.codes.UNAUTHORIZED:
            click.echo(f"Authentication failed with token on {api_url}")
            sys.exit(1)
        else:
            click.echo(
                f"Error connecting to ONEKEY platform: '{api_url}', error: {e.response.status_code}"
            )
            sys.exit(2)


cli.add_command(list_tenants)
cli.add_command(get_tenant_token)
cli.add_command(upload_firmware)
cli.add_command(ci_result)


def main():
    cli(auto_envvar_prefix="ONEKEY")


if __name__ == "__main__":
    main()
