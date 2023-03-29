import sys
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

import click
import httpx

from junit_xml import TestSuite, TestCase

from onekey_client import Client
from onekey_client.queries import load_query

FIRMWARE_STATUS_QUERY = load_query("get_firmware_latest_analysis_state.graphql")
GET_ALL_FIRMWARES = load_query("get_same_product_firmwares.graphql")
COMPARE_FIRMWARE = load_query("compare_firmware.graphql")
LATEST_ISSUES_QUERY = load_query("get_firmware_latest_results.graphql")


class ResultHandler:
    def __init__(
        self,
        client: Client,
        firmware_id: UUID,
        retry_count=10,
        retry_wait=60,
        check_interval=60,
    ):
        self.client = client
        self.firmware_id = str(firmware_id)
        self.retry_count = retry_count
        self.retry_wait = retry_wait
        self.check_interval = check_interval

    def get_result(self):
        error_count = 1

        while True:
            try:
                return self._get_result()
            except httpx.HTTPError as e:
                if error_count <= self.retry_count:
                    click.echo(
                        "Error communicating with ONEKEY platform, retrying; error='{}'".format(
                            str(e)
                        )
                    )
                    time.sleep(self.retry_wait * error_count)
                    error_count += 1
                else:
                    click.echo(
                        "Too many communication error with ONEKEY platform, failing"
                    )
                    raise

    def _get_result(self):
        self.wait_for_analysis_finish()

        recent_id = self.get_recent_firmware_id()
        if recent_id is not None:
            click.echo(
                f"Previous firmware results: {self.get_firmware_ui_url(recent_id)}"
            )
            res = self.client.query(
                COMPARE_FIRMWARE, {"base": recent_id, "other": self.firmware_id}
            )
            new_issues = res["compareFirmwareAnalyses"]["issues"]["new"]
            dropped_issues = res["compareFirmwareAnalyses"]["issues"]["dropped"]
            new_cves = {
                tuple(cve_entry.items())
                for cve_entry in res["compareFirmwareAnalyses"]["cveEntries"]["new"]
            }
            dropped_cves = {
                cve_entry["id"]
                for cve_entry in res["compareFirmwareAnalyses"]["cveEntries"]["dropped"]
            }
        else:
            click.echo("No previous firmware has been uploaded")
            res = self.client.query(LATEST_ISSUES_QUERY, {"id": self.firmware_id})
            new_issues = res["firmware"]["latestIssues"]
            dropped_issues = []
            new_cves = {
                tuple(cve_match["cve"].items())
                for cve_match in res["firmware"]["cveMatches"]
            }
            dropped_cves = []

        click.echo("#" * 80)
        click.echo(
            f"New / dropped issue count: {len(new_issues)} / {len(dropped_issues)}"
        )
        click.echo(f"New / dropped CVE count: {len(new_cves)} / {len(dropped_cves)}")
        if recent_id is not None and (
            new_issues or dropped_issues or new_cves or dropped_cves
        ):
            click.echo(
                f"Firmware comparison results with previous firmware: {self.get_firmware_compare_ui_url(recent_id, self.firmware_id)}"
            )
        else:
            click.echo("No changes since previous firmware")

        return new_issues, dropped_issues, new_cves, dropped_cves

    def wait_for_analysis_finish(self):
        click.echo(f"Waiting for analysis to finish on firmware: {self.firmware_id}")
        while True:
            try:
                self.client.refresh_tenant_token()

                res = self.client.query(FIRMWARE_STATUS_QUERY, {"id": self.firmware_id})
                if res["firmware"] is None:
                    click.echo(
                        "Firmware is not yet available, analysis not started yet, waiting."
                    )
                    time.sleep(self.check_interval)
                    continue

                latest_analysis = res["firmware"]["latestAnalysis"]
                if latest_analysis is None:
                    click.echo("Analysis has not started yet, waiting.")
                    time.sleep(self.check_interval)
                    continue

                if latest_analysis["state"] != "DONE":
                    click.echo("Firmware analysis still in progress, waiting.")
                    time.sleep(self.check_interval)
                    continue

                if latest_analysis["result"] != "COMPLETE":
                    click.echo(
                        f"Firmware analysis failed, check details: {self.get_firmware_ui_url(self.firmware_id)}"
                    )
                    sys.exit(2)
                else:
                    click.echo(
                        f"Firmware analysis finished successfully, results: {self.get_firmware_ui_url(self.firmware_id)}"
                    )
                    break
            except Exception as e:
                click.echo(f"Error fetching results {str(e)}")
                sys.exit(10)

    def get_recent_firmware_id(self):
        res = self.client.query(GET_ALL_FIRMWARES, {"id": self.firmware_id})

        firmware_ids = [
            timeline["firmware"]["id"]
            for timeline in res["firmware"]["product"]["firmwareTimeline"]
        ]

        latest_id = firmware_ids.pop(0)
        if latest_id != self.firmware_id:
            click.echo(
                f"Latest firmware upload is not the current firmware, skipping comparison with previous, latest={latest_id}"
            )
            return

        if not firmware_ids:
            click.echo("No previous firmware")
            return

        return firmware_ids[0]

    def get_firmware_ui_url(self, firmware_id):
        return f"https://{self.client.api_url.host}/firmwares?firmwareId={firmware_id}"

    def get_firmware_compare_ui_url(self, recent_id, firmware_id):
        return f"https://{self.client.api_url.host}/firmwares/compare-firmwares?baseFirmwareId={recent_id}&otherFirmwareId={firmware_id}"


class JUnitExporter:
    def __init__(self, client: Client, firmware_id: UUID):
        self.client = client
        self.firmware_id = str(firmware_id)

    def create_new_issue_testcase(self, issue):
        url = self.get_firmware_issues_ui_url()
        test_case = TestCase(
            name=issue["id"],
            classname=f"Issue: {issue['type']}",
            file=issue["file"]["path"],
            status="NEW",
            url=url,
        )

        test_case.add_failure_info(
            message="New issue",
            output=f"""New issue detected
    URL: {url}
    Type: {issue["type"]}
    Severity: {issue["severity"]}
    File: {issue["file"]["path"]}
    """,
        )
        return test_case

    def create_new_cve_testcase(self, cve):
        cve = dict(cve)
        url = self.get_firmware_cves_ui_url()
        test_case = TestCase(name=cve["id"], classname="CVE", status="NEW", url=url)
        test_case.add_failure_info(
            message="New CVE",
            output=f"""New CVE detected
    URL: {url}
    CVE ID: {cve['id']}
    Severity: {cve['severity']}
    Description: {cve['description']}
    """,
        )
        return test_case

    def generate_junit_xml(
        self, new_issues, dropped_issues, new_cves, dropped_cves, output_path: Path
    ):
        new_issues_test_cases = [
            self.create_new_issue_testcase(issue) for issue in new_issues
        ]

        dropped_issues_test_cases = [
            TestCase(
                name=issue["id"],
                classname=f"Issue: {issue['type']}",
                file=issue["file"]["path"],
                status="DROPPED",
                url=self.get_firmware_issues_ui_url(),
            )
            for issue in dropped_issues
        ]

        new_cves_test_cases = [self.create_new_cve_testcase(cve) for cve in new_cves]
        dropped_cves_test_cases = [
            TestCase(
                name=cve_id,
                classname="CVE",
                status="DROPPED",
                url=self.get_firmware_cves_ui_url(),
            )
            for cve_id in dropped_cves
        ]

        issues_test_suite = TestSuite(
            "ONEKEY identified issues",
            new_issues_test_cases + dropped_issues_test_cases,
        )
        cves_test_suite = TestSuite(
            "ONEKEY identified CVE entries",
            new_cves_test_cases + dropped_cves_test_cases,
        )
        with output_path.open("w") as f:
            TestSuite.to_file(f, [issues_test_suite, cves_test_suite])

    def get_firmware_issues_ui_url(self):
        return f"https://{self.client.api_url.host}/firmwares/issues?firmwareId={self.firmware_id}"

    def get_firmware_cves_ui_url(self):
        return f"https://{self.client.api_url.host}/firmwares/cves?firmwareId={self.firmware_id}"


@click.command()
@click.option("--firmware-id", required=True, type=UUID, help="Firmware ID")
@click.option(
    "--exit-code-on-new-finding",
    "exit_code",
    type=int,
    default=1,
    show_default=True,
    help="Exit code to use when findings are identified compared to previous firmware upload",
)
@click.option(
    "--check-interval",
    type=int,
    default=60,
    show_default=True,
    help="Wait time between checking for result",
)
@click.option(
    "--retry-count",
    type=int,
    default=10,
    show_default=True,
    help="Number of times to retry fetching results due to communication problem",
)
@click.option(
    "--retry-wait",
    type=int,
    default=60,
    show_default=True,
    help="Wait time between retries due to communication problem",
)
@click.option(
    "--junit-path",
    type=click.Path(exists=False, path_type=Path),
    help="File to export JUNIT xml",
)
@click.pass_obj
def ci_result(
    client: Client,
    firmware_id: UUID,
    exit_code: int,
    retry_count: int,
    retry_wait: int,
    check_interval: int,
    junit_path: Optional[Path],
):
    """Fetch analysis results for CI"""

    handler = ResultHandler(
        client,
        firmware_id,
        retry_count=retry_count,
        retry_wait=retry_wait,
        check_interval=check_interval,
    )
    new_issues, dropped_issues, new_cves, dropped_cves = handler.get_result()

    if junit_path is not None:
        junit_exporter = JUnitExporter(client, firmware_id)
        junit_exporter.generate_junit_xml(
            new_issues, dropped_issues, new_cves, dropped_cves, junit_path
        )

    exit_code = exit_code if new_issues or new_cves else 0

    sys.exit(exit_code)
