import json
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import Field

from zscaler_mcp.client import get_zscaler_client


JsonDict = Optional[Union[Dict[str, Any], str]]
JsonList = Optional[Union[List[Any], str]]


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


def _parse_list(value: JsonList) -> Optional[List[Any]]:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON list: {exc}") from exc
        if not isinstance(parsed, list):
            raise ValueError("JSON value must be a list")
        return parsed
    return list(value)


def zcc_create_trusted_network(
    name: Annotated[Optional[str], Field(description="Trusted network name.")] = None,
    payload: Annotated[
        JsonDict,
        Field(
            description=(
                "Trusted network request body. Use this for SDK/API fields not exposed "
                "as first-class tool parameters."
            )
        ),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
) -> Dict:
    """Create a ZCC trusted network (write operation)."""
    body = _parse_dict(payload)
    if name is not None:
        body["name"] = name
    if not body:
        raise ValueError("Supply name and/or payload")

    client = get_zscaler_client(service=service)
    created, _, err = client.zcc.trusted_networks.add_trusted_network(**body)
    if err:
        raise Exception(f"Failed to create ZCC trusted network: {err}")
    return _as_dict(created)


def zcc_update_trusted_network(
    network_id: Annotated[Union[int, str], Field(description="Trusted network ID.")],
    payload: Annotated[JsonDict, Field(description="Trusted network update body.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
) -> Dict:
    """Update a ZCC trusted network (write operation)."""
    if not network_id:
        raise ValueError("network_id is required")
    body = _parse_dict(payload)
    body.setdefault("id", network_id)

    client = get_zscaler_client(service=service)
    updated, _, err = client.zcc.trusted_networks.update_trusted_network(**body)
    if err:
        raise Exception(f"Failed to update ZCC trusted network {network_id}: {err}")
    return _as_dict(updated)


def zcc_delete_trusted_network(
    network_id: Annotated[Union[int, str], Field(description="Trusted network ID to delete.")],
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
    kwargs: str = "{}",
) -> str:
    """Delete a ZCC trusted network (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not network_id:
        raise ValueError("network_id is required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "zcc_delete_trusted_network", confirmed, {"network_id": str(network_id)}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    _, _, err = client.zcc.trusted_networks.delete_trusted_network(int(network_id))
    if err:
        raise Exception(f"Failed to delete ZCC trusted network {network_id}: {err}")
    return f"ZCC trusted network {network_id} deleted successfully."


def zcc_update_forwarding_profile(
    profile_id: Annotated[Union[int, str], Field(description="Forwarding profile ID.")],
    payload: Annotated[JsonDict, Field(description="Forwarding profile update body.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
) -> Dict:
    """Update a ZCC forwarding profile (write operation)."""
    if not profile_id:
        raise ValueError("profile_id is required")
    body = _parse_dict(payload)
    body.setdefault("id", profile_id)

    client = get_zscaler_client(service=service)
    updated, _, err = client.zcc.forwarding_profile.update_forwarding_profile(**body)
    if err:
        raise Exception(f"Failed to update ZCC forwarding profile {profile_id}: {err}")
    return _as_dict(updated)


def zcc_delete_forwarding_profile(
    profile_id: Annotated[Union[int, str], Field(description="Forwarding profile ID to delete.")],
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
    kwargs: str = "{}",
) -> str:
    """Delete a ZCC forwarding profile (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not profile_id:
        raise ValueError("profile_id is required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "zcc_delete_forwarding_profile", confirmed, {"profile_id": str(profile_id)}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    _, _, err = client.zcc.forwarding_profile.delete_forwarding_profile(int(profile_id))
    if err:
        raise Exception(f"Failed to delete ZCC forwarding profile {profile_id}: {err}")
    return f"ZCC forwarding profile {profile_id} deleted successfully."


def zcc_remove_devices(
    device_ids: Annotated[
        JsonList,
        Field(description="Optional list/JSON list of device IDs to remove."),
    ] = None,
    udids: Annotated[
        JsonList,
        Field(description="Optional list/JSON list of device UDIDs to remove."),
    ] = None,
    query_params: Annotated[JsonDict, Field(description="Optional SDK query parameters.")] = None,
    payload: Annotated[JsonDict, Field(description="Optional SDK request body fields.")] = None,
    force: Annotated[bool, Field(description="Use the SDK force_remove_devices operation.")] = False,
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
    kwargs: str = "{}",
) -> Union[Dict, str]:
    """Remove ZCC devices from the Client Connector portal (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    body = _parse_dict(payload)
    parsed_ids = _parse_list(device_ids)
    parsed_udids = _parse_list(udids)
    if parsed_ids is not None:
        body["device_ids"] = parsed_ids
    if parsed_udids is not None:
        body["udids"] = parsed_udids
    if not body and not query_params:
        raise ValueError("Supply device_ids, udids, query_params, or payload")

    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "zcc_remove_devices",
        confirmed,
        {"force": str(force), "device_ids": str(parsed_ids or ""), "udids": str(parsed_udids or "")},
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    api = client.zcc.devices
    operation = api.force_remove_devices if force else api.remove_devices
    result, _, err = operation(query_params=_parse_dict(query_params), **body)
    if err:
        raise Exception(f"Failed to remove ZCC devices: {err}")
    return _as_dict(result)


def zcc_remove_machine_tunnel(
    device_id: Annotated[Optional[Union[int, str]], Field(description="Optional device ID.")] = None,
    udid: Annotated[Optional[str], Field(description="Optional device UDID.")] = None,
    query_params: Annotated[JsonDict, Field(description="Optional SDK query parameters.")] = None,
    payload: Annotated[JsonDict, Field(description="Optional SDK request body fields.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
    kwargs: str = "{}",
) -> Union[Dict, str]:
    """Remove a ZCC machine tunnel from a device (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    body = _parse_dict(payload)
    if device_id is not None:
        body["device_id"] = device_id
    if udid is not None:
        body["udid"] = udid
    if not body and not query_params:
        raise ValueError("Supply device_id, udid, query_params, or payload")

    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "zcc_remove_machine_tunnel",
        confirmed,
        {"device_id": str(device_id or ""), "udid": str(udid or "")},
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    result, _, err = client.zcc.devices.remove_machine_tunnel(
        query_params=_parse_dict(query_params), **body
    )
    if err:
        raise Exception(f"Failed to remove ZCC machine tunnel: {err}")
    return _as_dict(result)


def zcc_update_device_cleanup_info(
    payload: Annotated[
        JsonDict,
        Field(description="Device cleanup settings body accepted by the ZCC SDK."),
    ],
    service: Annotated[str, Field(description="The service to use.")] = "zcc",
) -> Dict:
    """Update ZCC device cleanup settings (write operation)."""
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    result, _, err = client.zcc.devices.update_device_cleanup_info(**body)
    if err:
        raise Exception(f"Failed to update ZCC device cleanup info: {err}")
    return _as_dict(result)
