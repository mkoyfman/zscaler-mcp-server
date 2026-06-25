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


def ztw_list_admins(
    action: Annotated[
        str, Field(description="Action to perform: 'list_admins' or 'get_admin'.")
    ] = "list_admins",
    admin_id: Annotated[Optional[str], Field(description="Admin ID for get_admin action.")] = None,
    include_auditor_users: Annotated[
        Optional[bool], Field(description="Include / exclude auditor users in the response.")
    ] = None,
    include_admin_users: Annotated[
        Optional[bool], Field(description="Include / exclude admin users in the response.")
    ] = None,
    include_api_roles: Annotated[
        Optional[bool], Field(description="Include / exclude API roles in the response.")
    ] = None,
    search: Annotated[Optional[str], Field(description="The search string to filter by.")] = None,
    page: Annotated[Optional[int], Field(description="The page offset to return.")] = None,
    page_size: Annotated[
        Optional[int], Field(description="The number of records to return per page.")
    ] = None,
    version: Annotated[
        Optional[int], Field(description="Specifies the admins from a backup version.")
    ] = None,
    query: Annotated[
        Optional[str],
        Field(description="JMESPath expression for client-side filtering/projection of results."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Union[List[dict], dict, str]:
    """
    List all existing admin users or get details for a specific admin user in Zscaler Cloud & Branch Connector (ZTW).
    Supports JMESPath client-side filtering via the query parameter.

    Args:
        action (str): Action to perform: 'list_admins' or 'get_admin'. Defaults to 'list_admins'.
        admin_id (str, optional): Admin ID for get_admin action. Required when action is 'get_admin'.
        include_auditor_users (bool, optional): Include / exclude auditor users in the response.
        include_admin_users (bool, optional): Include / exclude admin users in the response.
        include_api_roles (bool, optional): Include / exclude API roles in the response.
        search (str, optional): The search string to filter by.
        page (int, optional): The page offset to return.
        page_size (int, optional): The number of records to return per page.
        version (int, optional): Specifies the admins from a backup version.
        service (str): The service to use. Defaults to "ztw".

    Returns:
        Union[List[dict], dict, str]: A list of admin users or a single admin user details.

    Examples:
        List all admins:

        >>> admins = ztw_list_admins()
        >>> print(f"Total admins found: {len(admins)}")
        >>> for admin in admins:
        ...     print(admin)

        List admins with specific filters:

        >>> admins = ztw_list_admins(
        ...     include_auditor_users=True,
        ...     include_admin_users=True,
        ...     include_api_roles=True
        ... )
        >>> print(f"Found {len(admins)} admins with specified filters")

        Search for admins:

        >>> admins = ztw_list_admins(search="admin")
        >>> print(f"Found {len(admins)} admins matching 'admin'")

        List admins with pagination:

        >>> admins = ztw_list_admins(page=1, page_size=10)
        >>> print(f"Found {len(admins)} admins on page 1")

        Get specific admin details:

        >>> admin = ztw_list_admins(action="get_admin", admin_id="123456789")
        >>> print(f"Admin details: {admin}")

        List admins from backup version:

        >>> admins = ztw_list_admins(version=1)
        >>> print(f"Found {len(admins)} admins from backup version 1")
    """
    client = get_zscaler_client(service=service)

    if action == "get_admin":
        if not admin_id:
            raise ValueError("admin_id is required when action is 'get_admin'")

        admin, _, err = client.ztw.admin_users.get_admin(admin_id)
        if err:
            raise Exception(f"Error getting ZTW admin {admin_id}: {err}")
        result = admin.as_dict()
        return apply_jmespath(result, query)

    elif action == "list_admins":
        query_params = {}
        if include_auditor_users is not None:
            query_params["include_auditor_users"] = include_auditor_users
        if include_admin_users is not None:
            query_params["include_admin_users"] = include_admin_users
        if include_api_roles is not None:
            query_params["include_api_roles"] = include_api_roles
        if search:
            query_params["search"] = search
        if page is not None:
            query_params["page"] = page
        if page_size is not None:
            query_params["page_size"] = page_size
        if version is not None:
            query_params["version"] = version

        admins, _, err = client.ztw.admin_users.list_admins(query_params=query_params)
        if err:
            raise Exception(f"Error listing ZTW admins: {err}")
        results = [a.as_dict() for a in admins]
        return apply_jmespath(results, query)

    else:
        raise ValueError(f"Invalid action '{action}'. Must be 'list_admins' or 'get_admin'")


# =============================================================================
# WRITE OPERATIONS
# =============================================================================


def ztw_create_admin(
    user_name: Annotated[str, Field(description="Admin display/user name.")],
    login_name: Annotated[str, Field(description="Admin login name.")],
    role: Annotated[str, Field(description="Admin role ID/name accepted by the SDK.")],
    email: Annotated[str, Field(description="Admin email address.")],
    password: Annotated[str, Field(description="Initial admin password.")],
    payload: Annotated[JsonDict, Field(description="Additional admin fields accepted by the SDK.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Create a ZTW admin user (write operation)."""
    if not all([user_name, login_name, role, email, password]):
        raise ValueError("user_name, login_name, role, email, and password are required")
    body = _parse_dict(payload)

    client = get_zscaler_client(service=service)
    admin, _, err = client.ztw.admin_users.add_admin(
        user_name=user_name,
        login_name=login_name,
        role=role,
        email=email,
        password=password,
        **body,
    )
    if err:
        raise Exception(f"Failed to create ZTW admin: {err}")
    return _as_dict(admin)


def ztw_update_admin(
    admin_id: Annotated[Union[int, str], Field(description="Admin ID to update.")],
    payload: Annotated[JsonDict, Field(description="Admin update body.")],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Update a ZTW admin user (write operation)."""
    if not admin_id:
        raise ValueError("admin_id is required")
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    admin, _, err = client.ztw.admin_users.update_admin(str(admin_id), **body)
    if err:
        raise Exception(f"Failed to update ZTW admin {admin_id}: {err}")
    return _as_dict(admin)


def ztw_delete_admin(
    admin_id: Annotated[Union[int, str], Field(description="Admin ID to delete.")],
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
    kwargs: str = "{}",
) -> str:
    """Delete a ZTW admin user (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not admin_id:
        raise ValueError("admin_id is required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "ztw_delete_admin", confirmed, {"admin_id": str(admin_id)}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    result = client.ztw.admin_users.delete_admin(str(admin_id))
    return f"ZTW admin {admin_id} deleted successfully. SDK result: {result}"


def ztw_change_admin_password(
    username: Annotated[str, Field(description="Admin username/login name.")],
    old_password: Annotated[str, Field(description="Current password.")],
    new_password: Annotated[str, Field(description="New password.")],
    payload: Annotated[JsonDict, Field(description="Additional SDK request fields.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "ztw",
) -> Dict:
    """Change a ZTW admin user's password (write operation)."""
    if not username or not old_password or not new_password:
        raise ValueError("username, old_password, and new_password are required")

    client = get_zscaler_client(service=service)
    result, _, err = client.ztw.admin_users.change_password(
        username, old_password, new_password, **_parse_dict(payload)
    )
    if err:
        raise Exception(f"Failed to change ZTW admin password for {username}: {err}")
    return _as_dict(result)
