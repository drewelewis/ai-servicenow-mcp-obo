import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_server_servicenow import cli


class StreamableHttpTests(unittest.TestCase):
    def test_cli_runs_streamable_http_transport(self):
        environment = {
            "SERVICENOW_INSTANCE_URL": "https://example.service-now.com/",
            "SERVICENOW_USERNAME": "test-user",
            "SERVICENOW_PASSWORD": "test-password",
        }
        observed = {}

        class StubServer:
            def __init__(self, instance_url, auth):
                observed["instance_url"] = instance_url
                observed["auth"] = auth

            def run(self, transport):
                observed["transport"] = transport

        with (
            patch.object(cli, "load_dotenv", return_value=False),
            patch.object(cli, "ServiceNowMCP", StubServer),
            patch.dict(cli.os.environ, environment, clear=True),
            patch.object(
                sys,
                "argv",
                ["mcp-server-servicenow", "--transport", "streamable-http"],
            ),
        ):
            cli.main()

        self.assertEqual(observed["instance_url"], "https://example.service-now.com/")
        self.assertEqual(observed["transport"], "streamable-http")

    def test_container_starts_with_streamable_http(self):
        dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"

        self.assertIn(
            'CMD ["python", "-m", "mcp_server_servicenow.cli", "--transport", "streamable-http"]',
            dockerfile.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()