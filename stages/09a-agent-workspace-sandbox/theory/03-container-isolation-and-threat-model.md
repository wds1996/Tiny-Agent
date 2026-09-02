# 03 — Container isolation and threat model

A child process shares the host kernel, filesystem visibility, user permissions, and environment unless you explicitly restrict them. Killing it on timeout improves resource control; it does not make it safe for hostile code.

A container adds namespaces/cgroups and can reduce privilege, but safe execution still depends on configuration and threat model.

## Tiny-Agent Docker baseline

`DockerSandboxRunner` builds a command containing:

```text
--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges
--pids-limit ...
--memory ...
--cpus ...
--user 65534:65534
--tmpfs /tmp:rw,noexec,nosuid,...
--volume <workspace>:/workspace:rw
```

The model command is passed as an argument vector after the image name. Tiny-Agent does not build:

```python
subprocess.run(f"docker ... {model_text}", shell=True)
```

## What remains

Depending on risk, production may still need:

- seccomp/AppArmor/SELinux profiles;
- rootless containers;
- gVisor/Kata/microVM/VM boundaries;
- signed/pinned images;
- image scanning;
- read-only dependency layers;
- per-task identities;
- explicit outbound proxies;
- stronger cross-tenant isolation.

## Default-deny network

Network access should be a capability, not an ambient assumption.

A coding task that needs only local tests can run with no network. A research task may need specific egress. Those are different policies.

The key security question is not:

> Does the Agent need internet?

It is:

> Which destination/protocol/credential does this exact task require, and what data may leave through it?
