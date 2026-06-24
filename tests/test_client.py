"""Tests for ``zscaler_mcp.client`` — the OneAPI client factory.

All Zscaler products are accessed through the unified OneAPI client
(``zscaler.ZscalerClient``), authenticated against ZIdentity.

This suite covers:

- explicit-argument client creation (with secret and with private key)
- the ``service="zpa"`` extra ``customer_id`` requirement
- environment-variable fallbacks for every required field
- explicit kwargs overriding env vars
- private-key fallback via ``ZSCALER_PRIVATE_KEY``
- ``user_agent_comment`` propagation
- error paths for missing credentials
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from zscaler_mcp.client import get_zscaler_client
from zscaler_mcp.request_credentials import (
    DelegatedZscalerCredentials,
    reset_delegated_credentials,
    set_delegated_credentials,
)


@patch("zscaler_mcp.client.load_dotenv")
class TestOneAPIExplicitArgs(unittest.TestCase):
    """The factory builds a config from explicit kwargs without touching env vars."""

    @patch("zscaler_mcp.client.ZscalerClient")
    def test_with_client_secret(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="cid",
            client_secret="csecret",
            vanity_domain="example.zscaler.com",
        )
        mock_client_cls.assert_called_once()
        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["clientId"], "cid")
        self.assertEqual(config["clientSecret"], "csecret")
        self.assertEqual(config["vanityDomain"], "example.zscaler.com")
        self.assertNotIn("privateKey", config)

    @patch("zscaler_mcp.client.ZscalerClient")
    def test_with_private_key(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="cid",
            client_secret="csecret",
            private_key="pk123",
            vanity_domain="example.zscaler.com",
        )
        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["privateKey"], "pk123")
        self.assertEqual(config["clientSecret"], "csecret")

    @patch("zscaler_mcp.client.ZscalerClient")
    def test_with_customer_id_and_cloud(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="cid",
            client_secret="csecret",
            customer_id="custid",
            vanity_domain="example.zscaler.com",
            cloud="beta",
        )
        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["customerId"], "custid")
        self.assertEqual(config["cloud"], "beta")

    @patch("zscaler_mcp.client.ZscalerClient")
    @patch.dict(os.environ, {}, clear=True)
    def test_no_customer_id_omitted(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="cid",
            client_secret="csecret",
            vanity_domain="example.zscaler.com",
        )
        config = mock_client_cls.call_args[0][0]
        self.assertNotIn("customerId", config)

    @patch("zscaler_mcp.client.ZscalerClient")
    @patch.dict(os.environ, {}, clear=True)
    def test_no_cloud_omitted(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="cid",
            client_secret="csecret",
            vanity_domain="example.zscaler.com",
        )
        config = mock_client_cls.call_args[0][0]
        self.assertNotIn("cloud", config)


@patch("zscaler_mcp.client.load_dotenv")
class TestZPACustomerIdRequirement(unittest.TestCase):
    """Calling a ZPA tool requires ``customer_id`` because the SDK enforces it."""

    def test_zpa_without_customer_id_raises(self, _dotenv):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                get_zscaler_client(
                    client_id="cid",
                    client_secret="csecret",
                    vanity_domain="example.zscaler.com",
                    service="zpa",
                )
            self.assertIn("ZSCALER_CUSTOMER_ID", str(ctx.exception))

    @patch("zscaler_mcp.client.ZscalerClient")
    def test_zpa_with_customer_id_passes(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="cid",
            client_secret="csecret",
            customer_id="custid",
            vanity_domain="example.zscaler.com",
            service="zpa",
        )
        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["customerId"], "custid")

    @patch("zscaler_mcp.client.ZscalerClient")
    def test_non_zpa_does_not_require_customer_id(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="cid",
            client_secret="csecret",
            vanity_domain="example.zscaler.com",
            service="zia",
        )
        mock_client_cls.assert_called_once()


@patch("zscaler_mcp.client.load_dotenv")
class TestMissingCredentials(unittest.TestCase):
    """Required OneAPI fields raise ``RuntimeError`` with a clear message."""

    def test_missing_client_id_raises(self, _dotenv):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                get_zscaler_client(
                    client_secret="csecret",
                    vanity_domain="example.zscaler.com",
                )
            self.assertIn("ZSCALER_CLIENT_ID", str(ctx.exception))

    def test_missing_vanity_domain_raises(self, _dotenv):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                get_zscaler_client(
                    client_id="cid",
                    client_secret="csecret",
                )
            self.assertIn("ZSCALER_VANITY_DOMAIN", str(ctx.exception))

    def test_missing_both_secret_and_key_raises(self, _dotenv):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                get_zscaler_client(
                    client_id="cid",
                    vanity_domain="example.zscaler.com",
                )
            self.assertIn("ZSCALER_CLIENT_SECRET", str(ctx.exception))
            self.assertIn("ZSCALER_PRIVATE_KEY", str(ctx.exception))


@patch("zscaler_mcp.client.load_dotenv")
class TestEnvVarFallbacks(unittest.TestCase):
    """The factory falls back to ``ZSCALER_*`` env vars when args are omitted."""

    @patch("zscaler_mcp.client.ZscalerClient")
    @patch.dict(
        os.environ,
        {
            "ZSCALER_CLIENT_ID": "env_cid",
            "ZSCALER_CLIENT_SECRET": "env_csecret",
            "ZSCALER_VANITY_DOMAIN": "env.zscaler.com",
            "ZSCALER_CLOUD": "beta",
        },
        clear=True,
    )
    def test_falls_back_to_env_vars(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client()
        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["clientId"], "env_cid")
        self.assertEqual(config["clientSecret"], "env_csecret")
        self.assertEqual(config["vanityDomain"], "env.zscaler.com")
        self.assertEqual(config["cloud"], "beta")

    @patch("zscaler_mcp.client.ZscalerClient")
    @patch.dict(
        os.environ,
        {
            "ZSCALER_CLIENT_ID": "env_cid",
            "ZSCALER_CLIENT_SECRET": "env_csecret",
            "ZSCALER_VANITY_DOMAIN": "env.zscaler.com",
            "ZSCALER_MCP_USER_AGENT_COMMENT": "TestAgent/1.0",
        },
        clear=True,
    )
    def test_user_agent_from_env(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client()
        config = mock_client_cls.call_args[0][0]
        self.assertIn("userAgent", config)

    @patch("zscaler_mcp.client.ZscalerClient")
    @patch.dict(
        os.environ,
        {
            "ZSCALER_CLIENT_ID": "env_cid",
            "ZSCALER_CLIENT_SECRET": "env_csecret",
            "ZSCALER_VANITY_DOMAIN": "env.zscaler.com",
        },
        clear=True,
    )
    def test_explicit_params_override_env(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client(
            client_id="override_cid",
            client_secret="override_csecret",
            vanity_domain="override.zscaler.com",
        )
        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["clientId"], "override_cid")
        self.assertEqual(config["clientSecret"], "override_csecret")
        self.assertEqual(config["vanityDomain"], "override.zscaler.com")

    @patch("zscaler_mcp.client.ZscalerClient")
    @patch.dict(
        os.environ,
        {
            "ZSCALER_CLIENT_ID": "cid",
            "ZSCALER_CLIENT_SECRET": "csecret",
            "ZSCALER_PRIVATE_KEY": "env_pk",
            "ZSCALER_VANITY_DOMAIN": "v.zscaler.com",
        },
        clear=True,
    )
    def test_private_key_from_env(self, mock_client_cls, _dotenv):
        mock_client_cls.return_value = MagicMock()
        get_zscaler_client()
        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["privateKey"], "env_pk")


@patch("zscaler_mcp.client.load_dotenv")
class TestDelegatedCredentials(unittest.TestCase):
    @patch("zscaler_mcp.client.ZscalerClient")
    @patch.dict(
        os.environ,
        {
            "ZSCALER_CLIENT_ID": "server-id",
            "ZSCALER_CLIENT_SECRET": "server-secret",
            "ZSCALER_PRIVATE_KEY": "server-private-key",
            "ZSCALER_VANITY_DOMAIN": "server-tenant",
            "ZSCALER_CUSTOMER_ID": "server-customer",
        },
        clear=True,
    )
    def test_delegated_values_replace_server_credentials(self, mock_client_cls, _dotenv):
        credentials = DelegatedZscalerCredentials(
            client_id="request-id",
            client_secret="request-secret",
            vanity_domain="request-tenant",
            customer_id="request-customer",
            cloud="beta",
        )
        token = set_delegated_credentials(credentials)
        try:
            get_zscaler_client(service="zpa")
        finally:
            reset_delegated_credentials(token)

        config = mock_client_cls.call_args[0][0]
        self.assertEqual(config["clientId"], "request-id")
        self.assertEqual(config["clientSecret"], "request-secret")
        self.assertEqual(config["vanityDomain"], "request-tenant")
        self.assertEqual(config["customerId"], "request-customer")
        self.assertNotIn("privateKey", config)

    @patch.dict(
        os.environ,
        {"ZSCALER_CUSTOMER_ID": "server-customer"},
        clear=True,
    )
    def test_missing_delegated_customer_does_not_use_server_customer(self, _dotenv):
        credentials = DelegatedZscalerCredentials(
            client_id="request-id",
            client_secret="request-secret",
            vanity_domain="request-tenant",
        )
        token = set_delegated_credentials(credentials)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                get_zscaler_client(service="zpa")
        finally:
            reset_delegated_credentials(token)

        self.assertIn("ZSCALER_CUSTOMER_ID", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
