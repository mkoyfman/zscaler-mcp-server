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


def ztw_list_roles(
    include_auditor_role: Annotated[
        Optional[bool],
        Field(description="Include or exclude auditor user information in the list."),
    ] = None,
    include_partner_role: Annotated[
        Optional[bool],
        Field(
            description="Include or exclude admin user information in the list. Default is True."
        ),
    ] = None,
    include_api_roles: Annotated[
        Optional[bool],
        Field(description="Include or exclude API role information in the list. Default is True."),
    ] = None,
    role_ids: Annotated[
        Optional[List[str]],
        Field(description="Include or exclude role ID information in the list."),
    ] = None,
    search: Annotated[
        Optional[str], Field(description="Search string to filter roles by name.")
    ] = None,
    query: Annotated[
        Optional[str],
        Field(description="JMESPath expression for client-side filtering/projection of results."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Union[List[dict], str]:
    """
    List all existing admin roles in Zscaler Cloud & Branch Connector (ZTW).
    Supports JMESPath client-side filtering via the query parameter.

    Args:
        include_auditor_role (bool, optional): Include or exclude auditor user information in the list.
        include_partner_role (bool, optional): Include or exclude admin user information in the list. Default is True.
        include_api_roles (bool, optional): Include or exclude API role information in the list. Default is True.
        role_ids (List[str], optional): Include or exclude role ID information in the list.
        search (str, optional): Search string to filter roles by name.
        service (str): The service to use. Defaults to "ztw".

    Returns:
        Union[List[dict], str]: A list containing all existing admin roles in ZTW.

    Examples:
        List all roles:

        >>> roles = ztw_list_roles()
        >>> print(f"Total roles found: {len(roles)}")
        >>> for role in roles:
        ...     print(role)

        List roles with specific filters:

        >>> roles = ztw_list_roles(
        ...     include_auditor_role=True,
        ...     include_partner_role=True,
        ...     include_api_roles=True
        ... )
        >>> print(f"Found {len(roles)} roles with specified filters")

        Search for roles by name:

        >>> roles = ztw_list_roles(search="admin")
        >>> print(f"Found {len(roles)} roles matching 'admin'")

        List specific roles by ID:

        >>> roles = ztw_list_roles(role_ids=["123456789", "987654321"])
        >>> print(f"Found {len(roles)} specific roles")
    """
    client = get_zscaler_client(service=service)

    query_params = {}
    if include_auditor_role is not None:
        query_params["include_auditor_role"] = include_auditor_role
    if include_partner_role is not None:
        query_params["include_partner_role"] = include_partner_role
    if include_api_roles is not None:
        query_params["include_api_roles"] = include_api_roles
    if role_ids:
        query_params["id"] = role_ids
    if search:
        query_params["search"] = search

    roles, _, err = client.ztw.admin_roles.list_roles(query_params=query_params)
    if err:
        raise Exception(f"Error listing ZTW admin roles: {err}")
    results = [r.as_dict() for r in roles]
    return apply_jmespath(results, query)


# =============================================================================
# WRITE OPERATIONS
# =============================================================================


def ztw_create_role(
    name: Annotated[str, Field(description="Role name.")],
    policy_access: Annotated[str, Field(description="Policy access level.")] = "NONE",
    report_access: Annotated[str, Field(description="Report access level.")] = "NONE",
    username_access: Annotated[str, Field(description="Username access level.")] = "NONE",
    dashboard_access: Annotated[str, Field(description="Dashboard access level.")] = "NONE",
    payload: Annotated[JsonDict, Field(description="Additional role fields accepted by the SDK.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Create a ZTW admin role (write operation)."""
    if not name:
        raise ValueError("name is required")
    body = _parse_dict(payload)

    client = get_zscaler_client(service=service)
    role, _, err = client.ztw.admin_roles.add_role(
        name=name,
        policy_access=policy_access,
        report_access=report_access,
        username_access=username_access,
        dashboard_access=dashboard_access,
        **body,
    )
    if err:
        raise Exception(f"Failed to create ZTW role: {err}")
    return _as_dict(role)


def ztw_update_role(
    role_id: Annotated[Union[int, str], Field(description="Role ID to update.")],
    payload: Annotated[JsonDict, Field(description="Role update body.")],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Update a ZTW admin role (write operation)."""
    if not role_id:
        raise ValueError("role_id is required")
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    role, _, err = client.ztw.admin_roles.update_role(str(role_id), **body)
    if err:
        raise Exception(f"Failed to update ZTW role {role_id}: {err}")
    return _as_dict(role)


def ztw_delete_role(
    role_id: Annotated[Union[int, str], Field(description="Role ID to delete.")],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
    kwargs: str = "{}",
) -> str:
    """Delete a ZTW admin role (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not role_id:
        raise ValueError("role_id is required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation("ztw_delete_role", confirmed, {"role_id": str(role_id)})
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    _, _, err = client.ztw.admin_roles.delete_role(str(role_id))
    if err:
        raise Exception(f"Failed to delete ZTW role {role_id}: {err}")
    return f"ZTW role {role_id} deleted successfully."
