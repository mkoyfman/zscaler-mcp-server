import json
from typing import Annotated, Any, Dict, Optional, Union

from pydantic import Field

from zscaler_mcp.client import get_zscaler_client


JsonDict = Optional[Union[Dict[str, Any], str]]


def _as_dict(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, list):
        return [_as_dict(v) for v in value]
    return value


def _parse_dict(value: JsonDict) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON object: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON payload must be an object")
        return parsed
    return dict(value)

# =============================================================================
# READ-ONLY OPERATIONS
# =============================================================================


def ztw_get_discovery_settings(
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """
    Retrieves the workload discovery service settings from Zscaler Cloud & Branch Connector (ZTW).
    This is a read-only operation.

    The workload discovery service settings control how Zscaler discovers and manages workloads
    in your cloud infrastructure. These settings include configuration for discovery roles,
    external IDs, and other discovery-related parameters.

    Args:
        service (str): The service to use (default: "ztw").

    Returns:
        dict: The discovery service settings object containing:
            - Configuration for workload discovery
            - Discovery role settings
            - External ID settings
            - Other discovery-related parameters

    Raises:
        Exception: If the discovery settings retrieval fails.

    Example:
        Get the current discovery service settings:
        >>> settings = ztw_get_discovery_settings()
        >>> print(f"Discovery settings: {settings}")
        >>> print(f"Discovery role: {settings.get('discovery_role', 'N/A')}")
    """
    client = get_zscaler_client(service=service)
    api = client.ztw.discovery_service

    settings, _, err = api.get_discovery_settings()
    if err:
        raise Exception(f"Failed to get ZTW discovery settings: {err}")

    return settings.as_dict()


# =============================================================================
# WRITE OPERATIONS
# =============================================================================


def ztw_update_discovery_service_permissions(
    account_group_id: Annotated[Union[int, str], Field(description="Account group ID.")],
    payload: Annotated[
        JsonDict,
        Field(description="Discovery service permission update body accepted by the ZTW SDK."),
    ],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Update ZTW discovery service permissions (write operation)."""
    if not account_group_id:
        raise ValueError("account_group_id is required")
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.discovery_service.update_discovery_service_permissions(
        int(account_group_id), **body
    )
    if err:
        raise Exception(
            f"Failed to update ZTW discovery permissions for account group {account_group_id}: {err}"
        )
    return _as_dict(result)
