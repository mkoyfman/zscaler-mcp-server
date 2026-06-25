"""Write-capable ZIA DLP dictionary and engine tools.

The existing ``get_zia_dlp_dictionaries`` and ``get_zia_dlp_engines``
manager tools are intentionally read-only.  This module adds verb-based
write tools for the common authoring workflow:

1. create/update a DLP dictionary;
2. create/update or augment a DLP engine expression;
3. attach the engine to a Web DLP policy rule;
4. locally simulate dictionary/expression matching before writing.

All mutating functions in this module are registered as write tools by
``ZIAService`` and therefore remain gated by
``ZSCALER_MCP_WRITE_ENABLED`` and ``ZSCALER_MCP_WRITE_TOOLS``.
"""

from __future__ import annotations

import ast
import html
import json
import re
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import Field

from zscaler_mcp.client import get_zscaler_client
from zscaler_mcp.utils.utils import parse_list


JsonList = Optional[Union[List[Any], str]]

_ENTRY_ACTIONS = {"all", "unique"}
_ENTRY_ACTION_ENUMS = {
    "phrase": {
        "all": "PHRASE_COUNT_TYPE_ALL",
        "unique": "PHRASE_COUNT_TYPE_UNIQUE",
    },
    "pattern": {
        "all": "PATTERN_COUNT_TYPE_ALL",
        "unique": "PATTERN_COUNT_TYPE_UNIQUE",
    },
}
_EXPRESSION_JOIN_OPERATORS = {"AND", "OR"}
_EXPRESSION_COMPARATORS = {">", ">=", "<", "<=", "==", "!="}


def _as_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def _normalize_phrase_match_type(value: str) -> str:
    """Accept friendly values and pass canonical API enums through."""
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered == "any":
        return "MATCH_ANY_CUSTOM_PHRASE_PATTERN_DICTIONARY"
    if lowered == "all":
        return "MATCH_ALL_CUSTOM_PHRASE_PATTERN_DICTIONARY"
    return normalized


def _normalize_entries(
    value: JsonList,
    *,
    text_key: str,
    default_action: str,
) -> Optional[List[tuple[str, str]]]:
    """Normalize phrases/patterns to the tuple shape expected by the SDK.

    Accepted forms:
    - ``["secret", "confidential"]``
    - ``[{"action": "all", "phrase": "secret"}]``
    - ``[["unique", "\\d{3}-\\d{2}-\\d{4}"]]``
    - JSON strings containing any of the above.
    """
    if value is None:
        return None
    parsed = parse_list(value)
    if not isinstance(parsed, list):
        raise ValueError(f"{text_key}s must be a list or JSON list string")

    entries: List[tuple[str, str]] = []
    for item in parsed:
        action = default_action
        text: Optional[str] = None

        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            action = str(item.get("action", default_action))
            text = item.get(text_key) or item.get("value") or item.get("text")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            action = str(item[0])
            text = str(item[1])
        else:
            raise ValueError(
                f"Invalid {text_key} entry {item!r}; use a string, "
                "{\"action\": ..., \"%s\": ...}, or [action, value]" % text_key
            )

        action = action.strip()
        lowered_action = action.lower()
        if lowered_action in _ENTRY_ACTIONS:
            action = _ENTRY_ACTION_ENUMS[text_key][lowered_action]
        elif not re.fullmatch(r"[A-Z][A-Z0-9_]*", action):
            raise ValueError(
                f"Invalid {text_key} action {action!r}; expected one of "
                f"{sorted(_ENTRY_ACTIONS)} or a canonical ZIA action enum"
            )
        if text is None or str(text) == "":
            raise ValueError(f"{text_key} entries cannot be empty")
        entries.append((action, str(text)))

    return entries


def _parse_optional_object(value: Optional[Union[Dict[str, Any], str]], field_name: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be a JSON object string") from exc
    else:
        parsed = value
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be an object/dict or JSON object string")
    return dict(parsed)


def _entries_to_payload(entries: Optional[List[tuple[str, str]]], text_key: str) -> Optional[List[dict]]:
    if entries is None:
        return None
    return [{"action": action, text_key: text} for action, text in entries]


def _execute_dlp_dictionary_write(
    api: Any,
    *,
    method: str,
    path_suffix: str = "",
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute dictionary writes directly so advanced payloads are not reshaped.

    The SDK's convenience methods reformat phrases/patterns from tuple
    inputs.  Direct execution keeps the MCP payload visible and lets callers
    pass exact API fields through ``payload_overrides`` when ZIA adds or
    changes enum values.
    """
    from zscaler.utils import format_url

    api_url = format_url(f"""
        {api._zia_base_endpoint}
        /dlpDictionaries{path_suffix}
    """)
    request, error = api._request_executor.create_request(
        method=method.upper(),
        endpoint=api_url,
        body=payload,
    )
    if error:
        raise Exception(f"Failed to build DLP dictionary request: {error}")
    response, error = api._request_executor.execute(request)
    if error:
        raise Exception(f"Failed to execute DLP dictionary request: {error}")
    body = response.get_body()
    return body if isinstance(body, dict) else {"result": body}


def _normalize_id_list(values: Optional[Union[List[Union[int, str]], str]]) -> List[Union[int, str]]:
    if values is None:
        return []
    parsed = parse_list(values)
    if not isinstance(parsed, list):
        parsed = [parsed]
    return parsed


def _extract_id(value: Any) -> Union[int, str]:
    if isinstance(value, dict):
        return value.get("id") or value.get("engine_id") or value.get("dict_id")
    return value


def _engine_ids_from_rule(rule: Dict[str, Any]) -> List[Union[int, str]]:
    ids: List[Union[int, str]] = []
    for item in rule.get("dlp_engines") or []:
        engine_id = _extract_id(item)
        if engine_id is not None and engine_id not in ids:
            ids.append(engine_id)
    return ids


def _html_unescape_expression(expression: Optional[str]) -> str:
    return html.unescape(expression or "").strip()


def _dictionary_term(dictionary_id: Union[int, str], comparator: str, threshold: int) -> str:
    if comparator not in _EXPRESSION_COMPARATORS:
        raise ValueError(
            f"Invalid comparator {comparator!r}; expected one of {sorted(_EXPRESSION_COMPARATORS)}"
        )
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 0:
        raise ValueError("threshold must be a non-negative integer")
    return f"(D{dictionary_id}.S {comparator} {threshold})"


def _append_dictionary_expression(
    existing_expression: Optional[str],
    *,
    dictionary_id: Union[int, str],
    comparator: str,
    threshold: int,
    join_operator: str,
) -> str:
    join_operator = join_operator.upper()
    if join_operator not in _EXPRESSION_JOIN_OPERATORS:
        raise ValueError(
            f"Invalid join_operator {join_operator!r}; expected AND or OR"
        )

    existing = _html_unescape_expression(existing_expression)
    term = _dictionary_term(dictionary_id, comparator, threshold)
    if not existing:
        return term
    if re.search(rf"\bD{re.escape(str(dictionary_id))}\.S\b", existing):
        return existing
    return f"({existing}) {join_operator} {term}"


def _validate_expression_if_requested(dlp_engine, expression: str, validate: bool) -> Optional[Dict[str, Any]]:
    if not validate:
        return None
    validation, _, err = dlp_engine.validate_dlp_expression(expression)
    if err:
        raise Exception(f"Failed to validate DLP engine expression: {err}")
    data = _as_dict(validation)
    status = str(data.get("status", "")).upper()
    err_msg = data.get("err_msg") or data.get("errMsg")
    if status and status not in {"VALID", "OK", "SUCCESS", "PASSED"} and err_msg:
        raise ValueError(f"DLP engine expression validation failed: {err_msg}")
    return data


def _safe_eval_expression(expression: str, counts: Dict[str, int]) -> tuple[bool, str]:
    """Evaluate a small DLP-expression subset against dictionary counts.

    Supports expressions such as ``((D63.S > 0) OR (D50.S > 0))``.
    This is intentionally not a general Python ``eval``: the AST is
    whitelisted after replacing D<id>.S tokens with integer counts.
    """
    expr = _html_unescape_expression(expression)
    substituted = re.sub(
        r"\bD(\d+)\.S\b",
        lambda m: str(counts.get(m.group(1), 0)),
        expr,
    )
    substituted = re.sub(r"\bAND\b", "and", substituted, flags=re.IGNORECASE)
    substituted = re.sub(r"\bOR\b", "or", substituted, flags=re.IGNORECASE)
    substituted = re.sub(r"\bNOT\b", "not", substituted, flags=re.IGNORECASE)

    tree = ast.parse(substituted, mode="eval")
    allowed_nodes = (
        ast.Expression,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Constant,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Gt,
        ast.GtE,
        ast.Lt,
        ast.LtE,
        ast.Eq,
        ast.NotEq,
        ast.Load,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"Unsupported expression element: {type(node).__name__}")
    return bool(eval(compile(tree, "<dlp-expression>", "eval"), {"__builtins__": {}}, {})), substituted


def zia_create_dlp_dictionary(
    name: Annotated[str, Field(description="Name of the custom DLP dictionary to create.")],
    phrases: Annotated[
        JsonList,
        Field(
            description=(
                "Optional phrases. Accepts a list/JSON list of strings, "
                "{action, phrase} objects, or [action, phrase] pairs. "
                "Actions: all, unique."
            )
        ),
    ] = None,
    patterns: Annotated[
        JsonList,
        Field(
            description=(
                "Optional regex patterns. Accepts a list/JSON list of strings, "
                "{action, pattern} objects, or [action, pattern] pairs. "
                "Actions: all, unique."
            )
        ),
    ] = None,
    description: Annotated[Optional[str], Field(description="Optional dictionary description.")] = None,
    custom_phrase_match_type: Annotated[
        str,
        Field(
            description=(
                "Dictionary match mode. Friendly values 'any'/'all' are accepted, "
                "or pass a canonical ZIA customPhraseMatchType enum."
            )
        ),
    ] = "any",
    dictionary_type: Annotated[
        str,
        Field(description="ZIA dictionaryType value."),
    ] = "PATTERNS_AND_PHRASES",
    payload_overrides: Annotated[
        Optional[Union[Dict[str, Any], str]],
        Field(
            description=(
                "Advanced exact API fields to merge into the create payload. "
                "Accepts an object or JSON object string. Use this only when "
                "ZIA requires a field/enum not yet surfaced as a first-class parameter."
            )
        ),
    ] = None,
    default_action: Annotated[
        str,
        Field(description="Default action for string-only phrase/pattern entries: all or unique."),
    ] = "all",
    service: Annotated[str, Field(description="The service to use.")] = "zia",
) -> dict:
    """Create a custom ZIA DLP dictionary (write operation)."""
    if not name:
        raise ValueError("name is required")
    normalized_phrases = _normalize_entries(
        phrases, text_key="phrase", default_action=default_action
    )
    normalized_patterns = _normalize_entries(
        patterns, text_key="pattern", default_action=default_action
    )
    advanced_payload = _parse_optional_object(payload_overrides, "payload_overrides")
    is_clone_payload = bool(
        advanced_payload.get("predefined_clone")
        or advanced_payload.get("predefinedClone")
        or advanced_payload.get("dict_template_id")
        or advanced_payload.get("dictTemplateId")
    )
    if not normalized_phrases and not normalized_patterns and not is_clone_payload:
        raise ValueError(
            "At least one phrase or pattern is required unless payload_overrides "
            "contains clone/template fields such as predefined_clone or dict_template_id"
        )

    payload: Dict[str, Any] = {
        "name": name,
        "customPhraseMatchType": _normalize_phrase_match_type(custom_phrase_match_type),
        "dictionaryType": dictionary_type,
    }
    if description is not None:
        payload["description"] = description
    if normalized_phrases is not None:
        payload["phrases"] = _entries_to_payload(normalized_phrases, "phrase")
    if normalized_patterns is not None:
        payload["patterns"] = _entries_to_payload(normalized_patterns, "pattern")
    payload.update(advanced_payload)

    client = get_zscaler_client(service=service)
    api = client.zia.dlp_dictionary
    return _execute_dlp_dictionary_write(
        api,
        method="post",
        payload=payload,
    )


def zia_update_dlp_dictionary(
    dict_id: Annotated[Union[int, str], Field(description="DLP dictionary ID to update.")],
    name: Annotated[Optional[str], Field(description="Optional replacement name.")] = None,
    phrases: Annotated[JsonList, Field(description="Optional full replacement phrase list.")] = None,
    patterns: Annotated[JsonList, Field(description="Optional full replacement pattern list.")] = None,
    description: Annotated[Optional[str], Field(description="Optional replacement description.")] = None,
    custom_phrase_match_type: Annotated[
        Optional[str],
        Field(description="Optional replacement customPhraseMatchType. Friendly any/all accepted."),
    ] = None,
    dictionary_type: Annotated[Optional[str], Field(description="Optional replacement dictionaryType.")] = None,
    payload_overrides: Annotated[
        Optional[Union[Dict[str, Any], str]],
        Field(
            description=(
                "Advanced exact API fields to merge into the update payload. "
                "Accepts an object or JSON object string."
            )
        ),
    ] = None,
    default_action: Annotated[
        str,
        Field(description="Default action for string-only phrase/pattern entries: all or unique."),
    ] = "all",
    service: Annotated[str, Field(description="The service to use.")] = "zia",
) -> dict:
    """Update a custom ZIA DLP dictionary (write operation, full replacement for supplied lists)."""
    if not dict_id:
        raise ValueError("dict_id is required")

    payload: Dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if custom_phrase_match_type is not None:
        payload["customPhraseMatchType"] = _normalize_phrase_match_type(custom_phrase_match_type)
    if dictionary_type is not None:
        payload["dictionaryType"] = dictionary_type
    if phrases is not None:
        payload["phrases"] = _entries_to_payload(
            _normalize_entries(phrases, text_key="phrase", default_action=default_action),
            "phrase",
        )
    if patterns is not None:
        payload["patterns"] = _entries_to_payload(
            _normalize_entries(patterns, text_key="pattern", default_action=default_action),
            "pattern",
        )
    payload.update(_parse_optional_object(payload_overrides, "payload_overrides"))
    if not payload:
        raise ValueError("At least one update field must be supplied")

    client = get_zscaler_client(service=service)
    api = client.zia.dlp_dictionary
    return _execute_dlp_dictionary_write(
        api,
        method="put",
        path_suffix=f"/{dict_id}",
        payload=payload,
    )


def zia_delete_dlp_dictionary(
    dict_id: Annotated[Union[int, str], Field(description="Custom DLP dictionary ID to delete.")],
    allow_predefined_dictionary_delete: Annotated[
        bool,
        Field(
            description=(
                "Allow delete attempt when the dictionary is not marked custom. "
                "Defaults to false because predefined dictionaries cannot normally be deleted."
            )
        ),
    ] = False,
    service: Annotated[str, Field(description="The service to use.")] = "zia",
    kwargs: str = "{}",
) -> str:
    """Delete a custom ZIA DLP dictionary (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not dict_id:
        raise ValueError("dict_id is required")

    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "zia_delete_dlp_dictionary", confirmed, {"dict_id": str(dict_id)}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    api = client.zia.dlp_dictionary

    existing_obj, _, err = api.get_dict(dict_id)
    if err:
        raise Exception(f"Failed to retrieve DLP dictionary {dict_id}: {err}")
    existing = _as_dict(existing_obj)
    if not existing.get("custom") and not allow_predefined_dictionary_delete:
        raise ValueError(
            f"DLP dictionary {dict_id} is not custom. Set "
            "allow_predefined_dictionary_delete=true only if you intentionally "
            "want to attempt deleting a non-custom/predefined dictionary."
        )

    _, _, err = api.delete_dict(dict_id)
    if err:
        raise Exception(f"Failed to delete DLP dictionary {dict_id}: {err}")
    return f"DLP dictionary {dict_id} deleted successfully."


def zia_create_dlp_engine(
    name: Annotated[str, Field(description="Name of the custom DLP engine to create.")],
    engine_expression: Annotated[
        str,
        Field(description="DLP expression, e.g. '((D63.S > 0) OR (D50.S > 0))'."),
    ],
    description: Annotated[Optional[str], Field(description="Optional engine description.")] = None,
    custom_dlp_engine: Annotated[
        bool, Field(description="Whether the engine is a custom DLP engine.")
    ] = True,
    validate_expression: Annotated[
        bool, Field(description="Validate expression with ZIA before create.")
    ] = True,
    service: Annotated[str, Field(description="The service to use.")] = "zia",
) -> dict:
    """Create a ZIA DLP engine (write operation)."""
    if not name:
        raise ValueError("name is required")
    if not engine_expression:
        raise ValueError("engine_expression is required")

    client = get_zscaler_client(service=service)
    api = client.zia.dlp_engine
    validation = _validate_expression_if_requested(api, engine_expression, validate_expression)

    payload: Dict[str, Any] = {
        "name": name,
        "engine_expression": engine_expression,
        "custom_dlp_engine": custom_dlp_engine,
    }
    if description is not None:
        payload["description"] = description

    created, _, err = api.add_dlp_engine(**payload)
    if err:
        raise Exception(f"Failed to create DLP engine: {err}")
    result = _as_dict(created)
    if validation is not None:
        result["_expression_validation"] = validation
    return result


def zia_delete_dlp_engine(
    engine_id: Annotated[Union[int, str], Field(description="Custom DLP engine ID to delete.")],
    allow_predefined_engine_delete: Annotated[
        bool,
        Field(
            description=(
                "Allow delete attempt when the engine is not marked custom. "
                "Defaults to false because predefined engines cannot normally be deleted."
            )
        ),
    ] = False,
    service: Annotated[str, Field(description="The service to use.")] = "zia",
    kwargs: str = "{}",
) -> str:
    """Delete a custom ZIA DLP engine (destructive write operation)."""
    from zscaler_mcp.common.elicitation import check_confirmation, extract_confirmed_from_kwargs

    if not engine_id:
        raise ValueError("engine_id is required")

    confirmed = extract_confirmed_from_kwargs(kwargs)
    confirmation_check = check_confirmation(
        "zia_delete_dlp_engine", confirmed, {"engine_id": str(engine_id)}
    )
    if confirmation_check:
        return confirmation_check

    client = get_zscaler_client(service=service)
    api = client.zia.dlp_engine

    existing_obj, _, err = api.get_dlp_engines(engine_id)
    if err:
        raise Exception(f"Failed to retrieve DLP engine {engine_id}: {err}")
    existing = _as_dict(existing_obj)
    if not existing.get("custom_dlp_engine") and not allow_predefined_engine_delete:
        raise ValueError(
            f"DLP engine {engine_id} is not custom. Set "
            "allow_predefined_engine_delete=true only if you intentionally "
            "want to attempt deleting a predefined engine."
        )

    _, _, err = api.delete_dlp_engine(engine_id)
    if err:
        raise Exception(f"Failed to delete DLP engine {engine_id}: {err}")
    return f"DLP engine {engine_id} deleted successfully."


def zia_attach_dictionary_to_engine(
    engine_id: Annotated[Union[int, str], Field(description="DLP engine ID to update.")],
    dictionary_id: Annotated[Union[int, str], Field(description="DLP dictionary ID to add to the expression.")],
    threshold: Annotated[int, Field(description="Match threshold for D<id>.S comparator.")] = 0,
    comparator: Annotated[
        str, Field(description="Comparator for the dictionary term: >, >=, <, <=, ==, !=")
    ] = ">",
    join_operator: Annotated[str, Field(description="How to join with existing expression: OR or AND.")] = "OR",
    validate_expression: Annotated[
        bool, Field(description="Validate the resulting expression with ZIA before update.")
    ] = True,
    allow_predefined_engine_update: Annotated[
        bool,
        Field(description="Allow update when the target engine is not custom. Defaults to false."),
    ] = False,
    service: Annotated[str, Field(description="The service to use.")] = "zia",
) -> dict:
    """Attach a dictionary to a DLP engine by updating its expression (write operation)."""
    client = get_zscaler_client(service=service)
    api = client.zia.dlp_engine

    existing_obj, _, err = api.get_dlp_engines(engine_id)
    if err:
        raise Exception(f"Failed to retrieve DLP engine {engine_id}: {err}")
    existing = _as_dict(existing_obj)
    if not existing.get("custom_dlp_engine") and not allow_predefined_engine_update:
        raise ValueError(
            f"DLP engine {engine_id} is not custom. Set "
            "allow_predefined_engine_update=true only if you intentionally "
            "want to attempt updating a predefined engine."
        )

    old_expression = existing.get("engine_expression")
    new_expression = _append_dictionary_expression(
        old_expression,
        dictionary_id=dictionary_id,
        comparator=comparator,
        threshold=threshold,
        join_operator=join_operator,
    )
    already_attached = _html_unescape_expression(old_expression) == new_expression
    if already_attached:
        return {
            "id": existing.get("id"),
            "name": existing.get("name"),
            "already_attached": True,
            "engine_expression": new_expression,
        }

    validation = _validate_expression_if_requested(api, new_expression, validate_expression)
    updated, _, err = api.update_dlp_engine(
        engine_id,
        name=existing.get("name"),
        description=existing.get("description"),
        engine_expression=new_expression,
        custom_dlp_engine=existing.get("custom_dlp_engine", True),
    )
    if err:
        raise Exception(f"Failed to attach dictionary {dictionary_id} to engine {engine_id}: {err}")

    result = _as_dict(updated)
    result["_previous_engine_expression"] = old_expression
    if validation is not None:
        result["_expression_validation"] = validation
    return result


def zia_attach_engine_to_policy(
    policy_rule_id: Annotated[
        Union[int, str],
        Field(description="Web DLP policy rule ID to update."),
    ],
    engine_id: Annotated[Union[int, str], Field(description="DLP engine ID to attach.")],
    policy_type: Annotated[
        str,
        Field(description="Policy type. Currently only 'web_dlp' is supported."),
    ] = "web_dlp",
    service: Annotated[str, Field(description="The service to use.")] = "zia",
) -> dict:
    """Attach a DLP engine to an existing Web DLP policy rule (write operation)."""
    if policy_type != "web_dlp":
        raise ValueError("Only policy_type='web_dlp' is currently supported")

    client = get_zscaler_client(service=service)
    api = client.zia.dlp_web_rules

    rule_obj, _, err = api.get_rule(policy_rule_id)
    if err:
        raise Exception(f"Failed to retrieve Web DLP rule {policy_rule_id}: {err}")
    rule = _as_dict(rule_obj)
    engine_ids = _engine_ids_from_rule(rule)
    if engine_id not in engine_ids and str(engine_id) not in {str(e) for e in engine_ids}:
        engine_ids.append(engine_id)
    else:
        return {
            "id": rule.get("id"),
            "name": rule.get("name"),
            "already_attached": True,
            "dlp_engines": engine_ids,
        }

    payload: Dict[str, Any] = {
        "name": rule.get("name"),
        "description": rule.get("description"),
        "action": rule.get("action"),
        "enabled": rule.get("state", "ENABLED") != "DISABLED",
        "rank": rule.get("rank"),
        "order": rule.get("order"),
        "dlp_engines": engine_ids,
    }

    # Preserve common scoping fields so PUT-style updates don't lose the
    # policy's existing match scope.
    for field in [
        "file_types",
        "cloud_applications",
        "locations",
        "location_groups",
        "groups",
        "departments",
        "users",
        "url_categories",
        "labels",
        "excluded_groups",
        "excluded_departments",
        "excluded_users",
        "dlp_content_locations_scopes",
        "workload_groups",
    ]:
        if field in rule:
            payload[field] = rule.get(field) or []

    updated, _, err = api.update_rule(policy_rule_id, **payload)
    if err:
        raise Exception(f"Failed to attach DLP engine {engine_id} to Web DLP rule {policy_rule_id}: {err}")

    result = _as_dict(updated)
    result["_previous_dlp_engines"] = _engine_ids_from_rule(rule)
    return result


def zia_simulate_dlp_match(
    content: Annotated[str, Field(description="Text content to test locally.")],
    dictionary_ids: Annotated[
        Optional[Union[List[Union[int, str]], str]],
        Field(description="Optional DLP dictionary IDs to fetch from ZIA and test."),
    ] = None,
    dictionaries: Annotated[
        JsonList,
        Field(
            description=(
                "Optional inline dictionary definitions. Each item should include "
                "id/name and phrases/patterns in the same shape returned by ZIA."
            )
        ),
    ] = None,
    engine_expression: Annotated[
        Optional[str],
        Field(description="Optional DLP engine expression to evaluate against match counts."),
    ] = None,
    case_sensitive: Annotated[bool, Field(description="Use case-sensitive phrase matching.")] = False,
    service: Annotated[str, Field(description="The service to use.")] = "zia",
) -> dict:
    """Locally simulate phrase/pattern dictionary matches and optional engine expression.

    This tool does **not** call a Zscaler write API.  If ``dictionary_ids``
    are supplied it reads those dictionaries, then performs local regex and
    phrase matching against ``content``.
    """
    if not content:
        raise ValueError("content is required")

    dictionary_defs: List[Dict[str, Any]] = []
    if dictionaries is not None:
        parsed = parse_list(dictionaries)
        if not isinstance(parsed, list):
            raise ValueError("dictionaries must be a list or JSON list string")
        dictionary_defs.extend(_as_dict(d) for d in parsed)

    ids = _normalize_id_list(dictionary_ids)
    if ids:
        client = get_zscaler_client(service=service)
        api = client.zia.dlp_dictionary
        for dict_id in ids:
            obj, _, err = api.get_dict(dict_id)
            if err:
                raise Exception(f"Failed to retrieve DLP dictionary {dict_id}: {err}")
            dictionary_defs.append(_as_dict(obj))

    if not dictionary_defs:
        raise ValueError("Supply at least one dictionary via dictionaries or dictionary_ids")

    flags = 0 if case_sensitive else re.IGNORECASE
    dictionary_results: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    for dictionary in dictionary_defs:
        dict_id = str(dictionary.get("id") or dictionary.get("dict_id") or dictionary.get("name"))
        phrase_hits = []
        pattern_hits = []

        for item in dictionary.get("phrases") or []:
            item_dict = _as_dict(item)
            phrase = item_dict.get("phrase") or item_dict.get("text") or item_dict.get("value")
            if phrase:
                occurrences = len(re.findall(re.escape(str(phrase)), content, flags))
                if occurrences:
                    phrase_hits.append({"phrase": phrase, "count": occurrences})

        for item in dictionary.get("patterns") or []:
            item_dict = _as_dict(item)
            pattern = item_dict.get("pattern") or item_dict.get("regex") or item_dict.get("value")
            if pattern:
                matches = re.findall(str(pattern), content, flags)
                if matches:
                    pattern_hits.append({"pattern": pattern, "count": len(matches)})

        count = sum(hit["count"] for hit in phrase_hits + pattern_hits)
        counts[dict_id] = count
        dictionary_results.append(
            {
                "id": dictionary.get("id"),
                "name": dictionary.get("name"),
                "count": count,
                "matched": count > 0,
                "phrase_hits": phrase_hits,
                "pattern_hits": pattern_hits,
            }
        )

    expression_result = None
    evaluated_expression = None
    if engine_expression:
        expression_result, evaluated_expression = _safe_eval_expression(engine_expression, counts)

    return {
        "matched": bool(expression_result) if engine_expression else any(r["matched"] for r in dictionary_results),
        "engine_expression_result": expression_result,
        "evaluated_expression": evaluated_expression,
        "dictionary_counts": counts,
        "dictionaries": dictionary_results,
    }
