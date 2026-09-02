# 02 — Files, artifacts, and workspace policy

A filesystem gives an Agent powerful external memory, but it also creates a new authorization boundary.

## Root the workspace

Never accept arbitrary absolute paths from the model and call `open()`.

Tiny-Agent uses:

```python
workspace.resolve("reports/result.md")
```

and verifies the resolved path remains inside the configured root.

This catches ordinary `../` traversal and symlink paths that resolve outside the workspace.

## Separate working files from promoted artifacts

During a task the Agent may create:

```text
scratch notes
intermediate code
logs
downloads
final report
```

Not every file should automatically become a user-visible artifact.

A production system should have an explicit promotion step:

```text
workspace file
-> validation/scanning/evaluation
-> artifact registry/object store
-> user/service exposure
```

## Limit reads as well as writes

Filesystem risk is not only overwriting `/etc/passwd`. Reading secrets is enough to cause harm if the Agent has any outbound channel.

A sandbox workspace should therefore mount only required inputs, not the developer's home directory.

## Context engineering connection

A workspace lets the Agent keep large state outside the prompt:

```text
file manifest
-> read relevant file on demand
-> edit artifact
```

This is often better than pasting an entire repository/document collection into every model call.
