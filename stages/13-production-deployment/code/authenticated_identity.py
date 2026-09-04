from tiny_agent.governance import Principal
from tiny_agent.service_identity import AuthenticatedIdentity, bind_trusted_identity


# Imagine this object came from validated JWT/mTLS/session middleware.
identity = AuthenticatedIdentity(
    principal=Principal("user-42", frozenset({"researcher"})),
    tenant_id="tenant-acme",
)

client_metadata = {
    "thread_id": "thread-123",
    "preferred_style": "concise",
}

bound = bind_trusted_identity(client_metadata, identity)
print(bound)

# The following would be rejected because body/client metadata is not allowed to
# impersonate the authenticated identity:
# bind_trusted_identity({"user_id": "admin"}, identity)
