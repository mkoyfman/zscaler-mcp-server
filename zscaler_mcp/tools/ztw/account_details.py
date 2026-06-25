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


def ztw_list_public_account_details(
    page: Annotated[Optional[int], Field(description="Page offset for paginated results.")] = None,
    page_size: Annotated[
        Optional[int],
        Field(description="Number of results per page. Default 250; maximum 1000."),
    ] = None,
    query: Annotated[
        Optional[str],
        Field(description="JMESPath expression for client-side filtering/projection of results."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> List[Dict]:
    """List public cloud account details from Zscaler Cloud & Branch Connector (ZTW).
    Supports JMESPath client-side filtering via the query parameter.

    Args:
        page: Optional page offset for paginated results.
        page_size: Optional page size (default 250, maximum 1000).
        service: The service to use (default: "ztw").

    Returns:
        List[Dict]: A list of public cloud account detail records.

    Raises:
        Exception: If the SDK reports an error.
    """

    client = get_zscaler_client(service=service)
    api = client.ztw.account_details

    query_params: Dict[str, object] = {}
    if page is not None:
        query_params["page"] = page
    if page_size is not None:
        query_params["page_size"] = page_size

    details, _, err = api.list_public_account_details(query_params=query_params)
    if err:
        raise Exception(f"Failed to list ZTW public account details: {err}")

    return apply_jmespath(details, query)


# =============================================================================
# WRITE OPERATIONS
# =============================================================================


def ztw_update_public_account_status(
    payload: Annotated[
        JsonDict,
        Field(description="Public account status update body accepted by the ZTW SDK."),
    ],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Update ZTW public account status (write operation)."""
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.account_details.update_public_account_status(**body)
    if err:
        raise Exception(f"Failed to update ZTW public account status: {err}")
    return _as_dict(result)
