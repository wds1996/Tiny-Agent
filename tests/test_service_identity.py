import pytest

from tiny_agent.governance import Principal
from tiny_agent.service_identity import (
    AuthenticatedIdentity,
    IdentityBindingError,
    ResourceOwner,
    bind_trusted_identity,
    require_owner,
)


def identity() -> AuthenticatedIdentity:
    return AuthenticatedIdentity(Principal("user-1", frozenset({"researcher"})), "tenant-a")


def test_client_cannot_supply_identity_fields() -> None:
    with pytest.raises(IdentityBindingError):
        bind_trusted_identity({"user_id": "admin"}, identity())
    bound = bind_trusted_identity({"thread_id": "t1"}, identity())
    assert bound["subject_id"] == "user-1"
    assert bound["tenant_id"] == "tenant-a"


def test_owner_scope_checks_tenant_and_subject() -> None:
    require_owner(identity(), ResourceOwner("user-1", "tenant-a"))
    with pytest.raises(IdentityBindingError):
        require_owner(identity(), ResourceOwner("user-1", "tenant-b"))
