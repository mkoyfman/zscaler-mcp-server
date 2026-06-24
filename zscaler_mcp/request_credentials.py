"""Request-scoped Zscaler credentials for delegated MCP authentication.

The HTTP auth middleware binds validated OneAPI credentials to a ContextVar for
the lifetime of one ASGI request. Tool code can then build its SDK client from
the caller's credentials without mutating process-wide environment variables.
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass
import os
import re
from typing import Optional

_VANITY_DOMAIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_CUSTOMER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SUPPORTED_CLOUDS = frozenset({"production", "beta"})


@dataclass(frozen=True)
class DelegatedZscalerCredentials:
    """Validated credentials and tenant routing supplied by an MCP client."""

    client_id: str
    client_secret: str
    vanity_domain: str
    customer_id: Optional[str] = None
    cloud: str = "production"

    def __post_init__(self) -> None:
        if not self.client_id.strip():
            raise ValueError("client_id must not be empty")
        if not self.client_secret:
            raise ValueError("client_secret must not be empty")
        if not _VANITY_DOMAIN_RE.fullmatch(self.vanity_domain):
            raise ValueError(
                "vanity_domain must be a 1-63 character ZIdentity tenant label "
                "containing only letters, numbers, and hyphens"
            )
        normalized_cloud = self.cloud.lower().strip()
        if normalized_cloud not in _SUPPORTED_CLOUDS:
            raise ValueError("cloud must be one of: production, beta")
        object.__setattr__(self, "cloud", normalized_cloud)
        if self.customer_id is not None and not _CUSTOMER_ID_RE.fullmatch(self.customer_id):
            raise ValueError(
                "customer_id must contain only letters, numbers, underscores, or hyphens"
            )


_delegated_credentials: ContextVar[Optional[DelegatedZscalerCredentials]] = ContextVar(
    "zscaler_delegated_credentials",
    default=None,
)


def set_delegated_credentials(
    credentials: DelegatedZscalerCredentials,
) -> Token[Optional[DelegatedZscalerCredentials]]:
    """Bind delegated credentials to the current request context."""
    return _delegated_credentials.set(credentials)


def reset_delegated_credentials(
    token: Token[Optional[DelegatedZscalerCredentials]],
) -> None:
    """Restore the request context after the downstream ASGI app completes."""
    _delegated_credentials.reset(token)


def get_delegated_credentials() -> Optional[DelegatedZscalerCredentials]:
    """Return credentials bound to the current request, if any."""
    return _delegated_credentials.get()


def resolve_zscaler_value(
    field: str,
    env_name: str,
    *,
    explicit: Optional[str] = None,
    default: Optional[str] = None,
) -> Optional[str]:
    """Resolve explicit, delegated, then process-wide Zscaler configuration.

    Once delegated credentials are present, missing delegated fields do not
    fall back to process environment variables. This fail-closed behavior
    prevents one caller's credentials from being combined with another
    tenant's process-wide customer ID or routing configuration.
    """
    if explicit not in (None, ""):
        return explicit

    delegated = get_delegated_credentials()
    if delegated is not None:
        value = getattr(delegated, field)
        return value if value not in (None, "") else default

    value = os.getenv(env_name)
    return value if value not in (None, "") else default


def get_customer_id() -> str:
    """Resolve the customer ID for tools that do not use the SDK factory."""
    return resolve_zscaler_value("customer_id", "ZSCALER_CUSTOMER_ID") or ""
