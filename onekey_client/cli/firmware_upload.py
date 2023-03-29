import sys
from pathlib import Path
from typing import Optional

import click

from onekey_client import FirmwareMetadata, Client
from onekey_client.errors import QueryError


@click.command()
@click.option(
    "--product", "product_name", required=True, help="Product name to add the firmware"
)
@click.option(
    "--vendor", "vendor_name", required=True, help="Vendor name to add the firmware"
)
@click.option(
    "--product-group",
    "product_group_name",
    default="Default",
    show_default=True,
    required=True,
    help="Product group name to add the firmware",
)
@click.option("--version", help="Firmware version")
@click.option("--name", help="Firmware name")
@click.argument("filename", type=click.Path(exists=True, path_type=Path))
@click.pass_obj
def upload_firmware(
    client: Client,
    product_name: str,
    vendor_name: str,
    product_group_name: str,
    version: Optional[str],
    name: Optional[str],
    filename: Path,
):
    """Uploads a firmware to the ONEKEY platform"""

    product_groups = client.get_product_groups()

    try:
        product_group_id = product_groups[product_group_name]
    except KeyError:
        click.echo(f"Missing product group: {product_group_name}")
        click.echo("Available product groups:")
        for pg in product_groups.keys():
            click.echo(f"- {pg}")
        sys.exit(10)

    if name is None:
        name = (
            f"{vendor_name}-{product_name}-{filename.name}"
            if version is None
            else f"{vendor_name}-{product_name}-{version}"
        )

    metadata = FirmwareMetadata(
        name=name,
        vendor_name=vendor_name,
        product_name=product_name,
        product_group_id=product_group_id,
        version=version,
    )

    try:
        res = client.upload_firmware(metadata, filename, enable_monitoring=False)
        click.echo(res["id"])
    except QueryError as e:
        click.echo("Error during firmware upload:")
        for error in e._errors:
            click.echo(f"- {error['message']}")
        sys.exit(11)
