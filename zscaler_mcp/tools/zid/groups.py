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


def _parse_list(value: JsonList) -> List[Any]:
    if value is None:
        return []
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


def zid_list_groups(
    query_params: Annotated[
        Optional[Dict],
        Field(description="Optional filters: offset, limit, name[like], exclude_dynamic_groups."),
    ] = None,
    query: Annotated[
        Optional[str],
        Field(description="JMESPath expression for client-side filtering/projection of results."),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> List[Dict]:
    """List Zidentity groups with optional filtering and pagination.

    Supports JMESPath client-side filtering via the query parameter.
    """
    client = get_zscaler_client(service=service)
    api = client.zid.groups

    query_params = query_params or {}
    groups_response, _, err = api.list_groups(query_params=query_params)
    if err:
        raise Exception(f"Failed to list groups: {err}")

    groups = groups_response.records if hasattr(groups_response, "records") else []
    results = [group.as_dict() for group in groups]
    return apply_jmespath(results, query)


def zid_get_group(
    group_id: Annotated[str, Field(description="Group ID.")],
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> Dict:
    """Get a specific Zidentity group by ID."""
    if not group_id:
        raise ValueError("group_id is required")

    client = get_zscaler_client(service=service)
    api = client.zid.groups

    group, _, err = api.get_group(group_id)
    if err:
        raise Exception(f"Failed to fetch group {group_id}: {err}")
    return group.as_dict()


def zid_search_groups(
    name: Annotated[
        str, Field(description="Group name to search for (case-insensitive partial match).")
    ],
    query_params: Annotated[
        Optional[Dict], Field(description="Optional filters for pagination.")
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> List[Dict]:
    """Search Zidentity groups by name using case-insensitive partial match."""
    if not name:
        raise ValueError("name is required for search")

    client = get_zscaler_client(service=service)
    api = client.zid.groups

    query_params = query_params or {}
    query_params["name[like]"] = name
    groups_response, _, err = api.list_groups(query_params=query_params)
    if err:
        raise Exception(f"Failed to search groups: {err}")

    groups = groups_response.records if hasattr(groups_response, "records") else []
    return [group.as_dict() for group in groups]


def zid_get_group_users(
    group_id: Annotated[str, Field(description="Group ID.")],
    query_params: Annotated[
        Optional[Dict],
        Field(
            description="Optional filters: offset, limit, login_name, login_name[like], display_name[like], primary_email[like], domain_name, idp_name."
        ),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> List[Dict]:
    """Get users in a specific Zidentity group by group ID."""
    if not group_id:
        raise ValueError("group_id is required")

    client = get_zscaler_client(service=service)
    api = client.zid.groups

    query_params = query_params or {}
    users_response, _, err = api.list_group_users_details(group_id, query_params=query_params)
    if err:
        raise Exception(f"Failed to fetch users for group {group_id}: {err}")

    users = users_response.records if hasattr(users_response, "records") else []
    return [user.as_dict() for user in users]


def zid_get_group_users_by_name(
    name: Annotated[str, Field(description="Group name to search for.")],
    query_params: Annotated[
        Optional[Dict], Field(description="Optional filters for pagination.")
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> List[Dict]:
    """Get users in a specific Zidentity group by group name (searches for group first)."""
    if not name:
        raise ValueError("name is required")

    client = get_zscaler_client(service=service)
    api = client.zid.groups

    # Search for the group by name using the name[like] filter
    search_params = query_params or {}
    search_params["name[like]"] = name

    groups_response, _, err = api.list_groups(query_params=search_params)
    if err:
        raise Exception(f"Failed to search for group '{name}': {err}")

    groups = groups_response.records if hasattr(groups_response, "records") else []

    if not groups:
        raise ValueError(f"Group '{name}' not found")

    # Use the first matching group's ID
    group_id = groups[0].id

    # Now get users using the found group ID
    user_query_params = query_params or {}
    # Remove the name[like] parameter as it's not valid for user queries
    user_query_params.pop("name[like]", None)

    users_response, _, err = api.list_group_users_details(group_id, query_params=user_query_params)
    if err:
        raise Exception(f"Failed to fetch users for group '{name}' (ID: {group_id}): {err}")

    users = users_response.records if hasattr(users_response, "records") else []
    return [user.as_dict() for user in users]


# =============================================================================
# WRITE OPERATIONS
# =============================================================================


def zid_create_group(
    name: Annotated[Optional[str], Field(description="Group name.")] = None,
    payload: Annotated[
        JsonDict,
        Field(
            description=(
                "ZIdentity group creation body. Use for SDK/API fields not exposed "
                "as first-class tool parameters."
            )
        ),
    ] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> Dict:
    """Create a ZIdentity group (write operation)."""
    body = _parse_dict(payload)
    if name is not None:
        body["name"] = name
    if not body:
        raise ValueError("Supply name and/or payload")

    client = get_zscaler_client(service=service)
    group, _, err = client.zid.groups.add_group(**body)
    if err:
        raise Exception(f"Failed to create ZIdentity group: {err}")
    return _as_dict(group)


def zid_update_group(
    group_id: Annotated[str, Field(description="Group ID to update.")],
    payload: Annotated[JsonDict, Field(description="ZIdentity group update body.")],
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> Dict:
    """Update a ZIdentity group (write operation)."""
    if not group_id:
        raise ValueError("group_id is required")
    body = _parse_dict(payload)
    if not body:
        raise ValueError("payload is required")

    client = get_zscaler_client(service=service)
    group, _, err = client.zid.groups.update_group(group_id, **body)
    if err:
        raise Exception(f"Failed to update ZIdentity group {group_id}: {err}")
    return _as_dict(group)


def zid_delete_group(
    group_id: Annotated[str, Field(description="Group ID to delete.")],
    service: Annotated[str, Field(description="The service to use.")] = "zid",
    kwargs: str = "{}",
) -> str:
    """Delete a ZIdentity group (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not group_id:
        raise ValueError("group_id is required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation("zid_delete_group", confirmed, {"group_id": group_id})
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    _, _, err = client.zid.groups.delete_group(group_id)
    if err:
        raise Exception(f"Failed to delete ZIdentity group {group_id}: {err}")
    return f"ZIdentity group {group_id} deleted successfully."


def zid_add_user_to_group(
    group_id: Annotated[str, Field(description="Group ID.")],
    user_id: Annotated[str, Field(description="User ID to add to the group.")],
    payload: Annotated[JsonDict, Field(description="Optional SDK request body fields.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> Dict:
    """Add one ZIdentity user to a group (write operation)."""
    if not group_id or not user_id:
        raise ValueError("group_id and user_id are required")

    client = get_zscaler_client(service=service)
    result, _, err = client.zid.groups.add_user_to_group(
        group_id, user_id, **_parse_dict(payload)
    )
    if err:
        raise Exception(f"Failed to add user {user_id} to group {group_id}: {err}")
    return _as_dict(result)


def zid_add_users_to_group(
    group_id: Annotated[str, Field(description="Group ID.")],
    user_ids: Annotated[JsonList, Field(description="List/JSON list of user IDs to add.")],
    payload: Annotated[JsonDict, Field(description="Optional SDK request body fields.")] = None,
    service: Annotated[str, Field(description="The service to use.")] = "zid",
) -> Dict:
    """Add multiple ZIdentity users to a group (write operation)."""
    if not group_id:
        raise ValueError("group_id is required")
    parsed_user_ids = _parse_list(user_ids)
    if not parsed_user_ids:
        raise ValueError("user_ids is required")
    body = _parse_dict(payload)
    body.setdefault("user_ids", parsed_user_ids)

    client = get_zscaler_client(service=service)
    result, _, err = client.zid.groups.add_users_to_group(group_id, **body)
    if err:
        raise Exception(f"Failed to add users to group {group_id}: {err}")
    return _as_dict(result)


def zid_remove_user_from_group(
    group_id: Annotated[str, Field(description="Group ID.")],
    user_id: Annotated[str, Field(description="User ID to remove from the group.")],
    service: Annotated[str, Field(description="The service to use.")] = "zid",
    kwargs: str = "{}",
) -> str:
    """Remove one ZIdentity user from a group (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not group_id or not user_id:
        raise ValueError("group_id and user_id are required")
    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "zid_remove_user_from_group", confirmed, {"group_id": group_id, "user_id": user_id}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    _, _, err = client.zid.groups.remove_user_from_group(group_id, user_id)
    if err:
        raise Exception(f"Failed to remove user {user_id} from group {group_id}: {err}")
    return f"ZIdentity user {user_id} removed from group {group_id} successfully."
