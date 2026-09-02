from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .governance import Principal


_RESERVED_IDENTITY_KEYS = frozenset({"subject_id", "tenant_id", "roles", "user_id"})


class IdentityBindingError(PermissionError):
    """Client metadata attempted to impersonate or cross an ownership boundary."""


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    principal: Principal
    tenant_id: str

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty")


@dataclass(frozen=True, slots=True)
class ResourceOwner:
    subject_id: str
    tenant_id: str


def bind_trusted_identity(
    client_metadata: Mapping[str, Any] | None,
    identity: AuthenticatedIdentity,
) -> dict[str, Any]:
    """Attach server-authenticated identity without trusting body-level identity fields."""

    metadata = dict(client_metadata or {})
    conflicting = _RESERVED_IDENTITY_KEYS.intersection(metadata)
    if conflicting:
        raise IdentityBindingError(
            f"client metadata may not supply reserved identity fields: {sorted(conflicting)}"
        )
    metadata.update(
        {
            "subject_id": identity.principal.subject_id,
            "tenant_id": identity.tenant_id,
            "roles": sorted(identity.principal.roles),
        }
    )
    return metadata


def require_owner(identity: AuthenticatedIdentity, owner: ResourceOwner) -> None:
    if (
        identity.principal.subject_id != owner.subject_id
        or identity.tenant_id != owner.tenant_id
    ):
        raise IdentityBindingError("authenticated principal does not own this resource")
