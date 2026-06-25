import json
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import Field

from zscaler_mcp.client import get_zscaler_client
from zscaler_mcp.common.jmespath_utils import apply_jmespath


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

# =============================================================================
# READ-ONLY OPERATIONS
# =============================================================================


def ztw_list_network_services(
    protocol: Annotated[
        Optional[str],
        Field(
            description="Filter by protocol (e.g., 'ICMP', 'TCP', 'UDP', 'GRE', 'ESP', 'OTHER')."
        ),
    ] = None,
    search: Annotated[
        Optional[str],
        Field(description="Optional search filter applied to the service name or description."),
    ] = None,
    locale: Annotated[
        Optional[str],
        Field(
            description="Optional locale for localized descriptions (e.g., 'en-US', 'de-DE', 'fr-FR')."
        ),
    ] = None,
    query: Annotated[
        Optional[str],
        Field(description="JMESPath expression for client-side filtering/projection of results."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> List[Dict]:
    """List network services configured in Zscaler Cloud & Branch Connector (ZTW).
    Supports JMESPath client-side filtering via the query parameter.

    Args:
        protocol: Optional network protocol filter.
        search: Optional search term for service name or description.
        locale: Optional locale code to localize descriptions.
        service: The service to use (default: "ztw").

    Returns:
        List[Dict]: A list of network service definitions.

    Raises:
        Exception: If the SDK returns an error response.
    """

    client = get_zscaler_client(service=service)
    api = client.ztw.nw_service

    query_params: Dict[str, object] = {}
    if protocol:
        query_params["protocol"] = protocol
    if search:
        query_params["search"] = search
    if locale:
        query_params["locale"] = locale

    services, _, err = api.list_network_services(query_params=query_params)
    if err:
        raise Exception(f"Failed to list ZTW network services: {err}")

    results = [svc.as_dict() for svc in services]
    return apply_jmespath(results, query)


# =============================================================================
# WRITE OPERATIONS
# =============================================================================


def ztw_create_network_service(
    name: Annotated[Optional[str], Field(description="Network service name.")] = None,
    ports: Annotated[
        JsonList,
        Field(description="Optional list/JSON list of port definitions accepted by the SDK."),
    ] = None,
    payload: Annotated[
        JsonDict,
        Field(description="Network service creation body accepted by the ZTW SDK."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Create a ZTW network service (write operation)."""
    body = _parse_dict(payload)
    if name is not None:
        body["name"] = name
    parsed_ports = _parse_list(ports)
    if not body and parsed_ports is None:
        raise ValueError("Supply name/payload and/or ports")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.nw_service.add_network_service(ports=parsed_ports, **body)
    if err:
        raise Exception(f"Failed to create ZTW network service: {err}")
    return _as_dict(result)


def ztw_update_network_service(
    service_id: Annotated[Union[int, str], Field(description="Network service ID.")],
    ports: Annotated[
        JsonList,
        Field(description="Optional replacement list/JSON list of port definitions."),
    ] = None,
    payload: Annotated[
        JsonDict,
        Field(description="Network service update body accepted by the ZTW SDK."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Update a ZTW network service (write operation)."""
    if not service_id:
        raise ValueError("service_id is required")
    body = _parse_dict(payload)
    parsed_ports = _parse_list(ports)
    if not body and parsed_ports is None:
        raise ValueError("Supply payload and/or ports")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.nw_service.update_network_service(
        str(service_id), ports=parsed_ports, **body
    )
    if err:
        raise Exception(f"Failed to update ZTW network service {service_id}: {err}")
    return _as_dict(result)


def ztw_delete_network_service(
    service_id: Annotated[Union[int, str], Field(description="Network service ID to delete.")],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
    kwargs: str = "{}",
) -> str:
    """Delete a ZTW network service (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not service_id:
        raise ValueError("service_id is required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "ztw_delete_network_service", confirmed, {"service_id": str(service_id)}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    _, _, err = client.ztw.nw_service.delete_network_service(int(service_id))
    if err:
        raise Exception(f"Failed to delete ZTW network service {service_id}: {err}")
    return f"ZTW network service {service_id} deleted successfully."
