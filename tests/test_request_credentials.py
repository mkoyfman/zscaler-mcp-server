"""Tests for request-scoped delegated Zscaler credentials."""

import pytest

from zscaler_mcp.request_credentials import (
    DelegatedZscalerCredentials,
    get_customer_id,
    get_delegated_credentials,
    reset_delegated_credentials,
    resolve_zscaler_value,
    set_delegated_credentials,
)


def _credentials(**overrides):
    values = {
        "client_id": "request-id",
        "client_secret": "request-secret",
        "vanity_domain": "request-tenant",
        "customer_id": "request-customer",
        "cloud": "production",
    }
    values.update(overrides)
    return DelegatedZscalerCredentials(**values)


def test_context_is_bound_and_reset():
    credentials = _credentials()
    token = set_delegated_credentials(credentials)
    try:
        assert get_delegated_credentials() == credentials
        assert get_customer_id() == "request-customer"
    finally:
        reset_delegated_credentials(token)

    assert get_delegated_credentials() is None


def test_delegated_value_overrides_environment(monkeypatch):
    monkeypatch.setenv("ZSCALER_CLIENT_ID", "server-id")
    token = set_delegated_credentials(_credentials())
    try:
        assert resolve_zscaler_value("client_id", "ZSCALER_CLIENT_ID") == "request-id"
    finally:
        reset_delegated_credentials(token)


def test_missing_delegated_field_does_not_fall_back_to_environment(monkeypatch):
    monkeypatch.setenv("ZSCALER_CUSTOMER_ID", "server-customer")
    token = set_delegated_credentials(_credentials(customer_id=None))
    try:
        assert get_customer_id() == ""
    finally:
        reset_delegated_credentials(token)


def test_customer_id_allows_zscaler_domain_style_values():
    credentials = _credentials(customer_id="zscalerthree.net-177954596")

    assert credentials.customer_id == "zscalerthree.net-177954596"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vanity_domain", "tenant.example.com"),
        ("vanity_domain", "../tenant"),
        ("customer_id", "customer/other"),
        ("cloud", "evil.example.com"),
    ],
)
def test_invalid_routing_values_are_rejected(field, value):
    with pytest.raises(ValueError):
        _credentials(**{field: value})
