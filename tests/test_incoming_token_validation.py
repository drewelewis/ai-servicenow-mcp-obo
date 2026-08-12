import time
import unittest
from unittest.mock import Mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from mcp_server_servicenow.server import (
    EntraTokenValidator,
    IncomingTokenValidationError,
    create_servicenow_jwt_bearer_user_auth,
)


class IncomingTokenValidationTests(unittest.TestCase):
    def setUp(self):
        self.tenant_id = "00000000-0000-0000-0000-000000000001"
        self.client_id = "00000000-0000-0000-0000-000000000002"
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.validator = EntraTokenValidator(
            tenant_id=self.tenant_id,
            expected_audiences=[self.client_id, f"api://{self.client_id}"],
        )
        signing_key = Mock()
        signing_key.key = self.private_key.public_key()
        self.validator.jwks_client.get_signing_key_from_jwt = Mock(return_value=signing_key)

    def _token(self, audience):
        now = int(time.time())
        return jwt.encode(
            {
                "aud": audience,
                "exp": now + 300,
                "iat": now,
                "iss": f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",
                "oid": "00000000-0000-0000-0000-000000000003",
                "tid": self.tenant_id,
            },
            self.private_key,
            algorithm="RS256",
        )

    def test_accepts_bare_and_identifier_uri_audiences(self):
        for audience in (self.client_id, f"api://{self.client_id}"):
            with self.subTest(audience=audience):
                claims = self.validator.validate(self._token(audience))
                self.assertEqual(audience, claims["aud"])

    def test_rejects_unrelated_audience(self):
        with self.assertRaises(IncomingTokenValidationError):
            self.validator.validate(self._token("api://unrelated-client"))

    def test_servicenow_jwt_factory_accepts_both_audience_forms_by_default(self):
        auth = create_servicenow_jwt_bearer_user_auth(
            tenant_id=self.tenant_id,
            upstream_client_id=self.client_id,
            jwt_client_id="servicenow-client-id",
            token_endpoint="https://example.service-now.com/oauth_token.do",
            instance_url="https://example.service-now.com",
            jwt_private_key="test-private-key",
        )

        self.assertEqual(
            [self.client_id, f"api://{self.client_id}"],
            auth._validator.expected_audiences,
        )


if __name__ == "__main__":
    unittest.main()