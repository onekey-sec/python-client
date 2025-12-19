import sys
from pathlib import Path

import click

from onekey_client import Client, FirmwareMetadata
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
@click.option(
    "--analysis-configuration",
    "analysis_configuration_name",
    default="Default",
    show_default=True,
    required=True,
    help="Analysis configuration name",
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
    analysis_configuration_name: str,
    version: str | None,
    name: str | None,
    filename: Path,
):
    """Upload a firmware to the ONEKEY platform."""
    product_group_id = _get_product_group_id_by_name(client, product_group_name)
    analysis_configuration_id = _get_analysis_configuration_id_by_name(
        client, analysis_configuration_name
    )

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
        analysis_configuration_id=analysis_configuration_id,
    )

    try:
        res = client.upload_firmware(metadata, filename, enable_monitoring=False)
        click.echo(res["id"])
    except QueryError as e:
        click.echo("Error during firmware upload:")
        for error in e.errors:
            click.echo(f"- {error['message']}")
        sys.exit(11)


def _get_product_group_id_by_name(client: Client, product_group_name: str):
    product_groups = client.get_product_groups()

    try:
        return product_groups[product_group_name]
    except KeyError:
        click.echo(f"Missing product group: {product_group_name}")
        click.echo("Available product groups:")
        for pg in product_groups.keys():
            click.echo(f"- {pg}")
        sys.exit(10)


def _get_analysis_configuration_id_by_name(
    client: Client, analysis_configuration_name: str
):
    analysis_configurations = client.get_analysis_configurations()

    try:
        return analysis_configurations[analysis_configuration_name]
    except KeyError:
        click.echo(f"Missing analysis configuration {analysis_configuration_name}")
        click.echo("Available analysis configurations:")
        for config in analysis_configurations.keys():
            click.echo(f"- {config}")
        sys.exit(12)
