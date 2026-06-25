import json
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import Field

from zscaler_mcp.client import get_zscaler_client
from zscaler_mcp.common.jmespath_utils import apply_jmespath


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


def ztw_list_public_cloud_info(
    page: Annotated[
        Optional[int], Field(description="Page offset for paginated results. The default is 0.")
    ] = None,
    page_size: Annotated[
        Optional[int],
        Field(description="Number of results per page. Default is 100; maximum is 1000."),
    ] = None,
    search: Annotated[
        Optional[str], Field(description="Optional search filter for account name or metadata.")
    ] = None,
    cloud_type: Annotated[
        Optional[str], Field(description="Cloud provider filter (e.g., 'AWS', 'AZURE', 'GCP').")
    ] = None,
    query: Annotated[
        Optional[str],
        Field(description="JMESPath expression for client-side filtering/projection of results."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> List[Dict]:
    """List Zscaler Public Cloud (ZTW) accounts with optional filtering.

    This tool queries the Zscaler Cloud & Branch Connector (ZTW) public cloud information
    endpoint and returns account metadata such as account IDs, regions, and integration details.
    Supports JMESPath client-side filtering via the query parameter.

    Args:
        page: Page offset for paginated results.
        page_size: Number of results per page (default 100, maximum 1000).
        search: Optional search filter applied to account metadata.
        cloud_type: Optional cloud provider filter (AWS, AZURE, or GCP).
        service: The service to use (default: "ztw").

    Returns:
        List[Dict]: A list of public cloud account records.

    Raises:
        Exception: If the Zscaler SDK reports an error.
    """

    client = get_zscaler_client(service=service)
    api = client.ztw.public_cloud_info

    query_params: Dict[str, object] = {}
    if page is not None:
        query_params["page"] = page
    if page_size is not None:
        query_params["page_size"] = page_size
    if search:
        query_params["search"] = search
    if cloud_type:
        query_params["cloud_type"] = cloud_type

    accounts, _, err = api.list_public_cloud_info(query_params=query_params)
    if err:
        raise Exception(f"Failed to list ZTW public cloud info: {err}")

    results = [account.as_dict() for account in accounts]
    return apply_jmespath(results, query)


# =============================================================================
# WRITE OPERATIONS
# =============================================================================


def ztw_create_public_cloud_info(
    payload: Annotated[
        JsonDict,
        Field(description="Public cloud account creation body accepted by the ZTW SDK."),
    ],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Create ZTW public cloud account info (write operation)."""
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.public_cloud_info.add_public_cloud_info(**body)
    if err:
        raise Exception(f"Failed to create ZTW public cloud info: {err}")
    return _as_dict(result)


def ztw_update_public_cloud_info(
    cloud_id: Annotated[Union[int, str], Field(description="Public cloud account/info ID.")],
    payload: Annotated[
        JsonDict,
        Field(description="Public cloud account update body accepted by the ZTW SDK."),
    ],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Update ZTW public cloud account info (write operation)."""
    if not cloud_id:
        raise ValueError("cloud_id is required")
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.public_cloud_info.update_public_cloud_info(
        int(cloud_id), **body
    )
    if err:
        raise Exception(f"Failed to update ZTW public cloud info {cloud_id}: {err}")
    return _as_dict(result)


def ztw_delete_public_cloud_info(
    cloud_id: Annotated[Union[int, str], Field(description="Public cloud account/info ID.")],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
    kwargs: str = "{}",
) -> str:
    """Delete ZTW public cloud account info (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not cloud_id:
        raise ValueError("cloud_id is required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "ztw_delete_public_cloud_info", confirmed, {"cloud_id": str(cloud_id)}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    _, _, err = client.ztw.public_cloud_info.delete_public_cloud_info(int(cloud_id))
    if err:
        raise Exception(f"Failed to delete ZTW public cloud info {cloud_id}: {err}")
    return f"ZTW public cloud info {cloud_id} deleted successfully."


def ztw_change_public_cloud_info_state(
    cloud_id: Annotated[Union[int, str], Field(description="Public cloud account/info ID.")],
    payload: Annotated[JsonDict, Field(description="State-change body accepted by the ZTW SDK.")],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Change ZTW public cloud account state (write operation)."""
    if not cloud_id:
        raise ValueError("cloud_id is required")
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.public_cloud_info.change_state_public_cloud_info(
        int(cloud_id), **body
    )
    if err:
        raise Exception(f"Failed to change ZTW public cloud info {cloud_id} state: {err}")
    return _as_dict(result)


def ztw_generate_public_cloud_external_id(
    payload: Annotated[
        JsonDict,
        Field(description="External ID generation body accepted by the ZTW SDK."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Generate a ZTW public-cloud external ID (write/helper operation)."""
    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.public_cloud_info.generate_external_id(**_parse_dict(payload))
    if err:
        raise Exception(f"Failed to generate ZTW public cloud external ID: {err}")
    return _as_dict(result)
