import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AzdEntraHookTests(unittest.TestCase):
    def test_azure_yaml_runs_entra_preprovision_hook(self):
        manifest = (ROOT / "azure.yaml").read_text(encoding="utf-8")

        self.assertIn("preprovision:", manifest)
        self.assertIn("./scripts/azd-preprovision.js", manifest)
        self.assertIn("continueOnError: false", manifest)

    def test_python_package_discovery_excludes_infrastructure(self):
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('[tool.setuptools.packages.find]', project)
        self.assertIn('include = ["mcp_server_servicenow*"]', project)

    def test_bootstrap_provisions_copilot_studio_client_for_azd(self):
        bootstrap = (ROOT / "scripts" / "bootstrap-entra-obo.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("servicenow-mcp-copilot-studio-client", bootstrap)
        self.assertIn("COPILOT_STUDIO_CLIENT_ID", bootstrap)
        self.assertIn("COPILOT_STUDIO_CLIENT_SECRET", bootstrap)
        self.assertIn("COPILOT_STUDIO_REFRESH_URL", bootstrap)
        self.assertIn("COPILOT_STUDIO_REDIRECT_URI", bootstrap)
        self.assertIn("Update-LocalEnvFile", bootstrap)
        self.assertIn('$lines = @(if (Test-Path -Path $Path)', bootstrap)
        self.assertIn("$repositoryRoot = Split-Path -Parent $PSScriptRoot", bootstrap)
        self.assertIn("ConfigureAzdEnvironment", bootstrap)
        self.assertIn("RotateSecrets", bootstrap)
        self.assertNotIn(".env.obo.generated", bootstrap)
        self.assertNotIn("OutputEnvFile", bootstrap)

    def test_servicenow_setup_uses_only_root_env(self):
        setup = (ROOT / "scripts" / "service_now_setup.py").read_text(
            encoding="utf-8"
        )
        bootstrap = (ROOT / "scripts" / "bootstrap_servicenow_jwt.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("servicenow-jwt-bootstrap.env", setup)
        self.assertNotIn("servicenow-jwt-bootstrap.env", bootstrap)
        self.assertIn('default=str(REPO_ROOT / ".env")', bootstrap)
        self.assertFalse((ROOT / "scripts" / ".env").exists())


if __name__ == "__main__":
    unittest.main()