# 03 — Container Isolation and Threat Modeling

A child process shares the host kernel and inherits ambient authority unless you remove it. A container adds isolation mechanisms, but security depends on configuration and threat model.

The question is not:

> Is Docker safe?

The useful question is:

> Safe enough against which attacker, with which data/credentials/network access, under which runtime configuration?

---

## 1. Tiny-Agent's Docker baseline

`DockerSandboxRunner` builds a command shaped like:

```text
docker run --rm
  --read-only
  --cap-drop ALL
  --security-opt no-new-privileges
  --pids-limit 128
  --memory 512m
  --cpus 1.0
  --user 65534:65534
  --tmpfs /tmp:rw,noexec,nosuid,size=64m
  --volume <workspace>:/workspace:rw
  --workdir /workspace
  --network none
  python:3.12-slim
  <argv...>
```

Each flag addresses a different failure mode.

---

## 2. Read-only root filesystem

```text
--read-only
```

reduces the files a process can modify inside the container image.

The workspace is mounted separately as writable because the task may need artifacts.

This creates a useful split:

```text
runtime/dependencies -> read-only
working artifacts    -> explicit writable mount
```

---

## 3. Drop capabilities and privilege escalation

```text
--cap-drop ALL
--security-opt no-new-privileges
--user 65534:65534
```

reduce Linux privileges compared with a default/root process.

Do not run model-generated code as root merely because the container will be deleted later. A temporary root problem is still a root problem; it is simply punctual.

---

## 4. Bound resource exhaustion

Model-generated code can accidentally or deliberately consume resources.

```text
while True: spawn_process()
allocate_gigabytes()
infinite_loop()
```

Tiny-Agent uses:

```text
PID limit
memory limit
CPU limit
wall-clock timeout
output-size cap
```

No single limit solves everything. Together they bound common denial-of-service paths.

---

## 5. Network is disabled by default

```text
--network none
```

Why?

A local code/test task often needs no network. Removing ambient egress prevents many exfiltration/download paths by construction.

If a task needs network, prefer an explicit policy:

```text
which destination?
which protocol?
which credential?
what data may leave?
what logging/audit applies?
```

"Needs internet" is usually too broad a requirement.

---

## 6. Never build shell strings from model text

Bad:

```python
subprocess.run(
    f"docker run ... {model_command}",
    shell=True,
)
```

Now shell metacharacters become another attack surface.

Tiny-Agent accepts an argument vector:

```python
result = runner.run([
    "python",
    "-c",
    "print('sandbox-ok')",
])
```

The Docker CLI and container process receive explicit arguments rather than a host-shell interpolation string.

---

## 7. Ordinary Docker is not the final word

Higher-risk workloads may need:

- custom seccomp profiles;
- AppArmor/SELinux;
- rootless runtimes;
- gVisor/Kata-style stronger boundaries;
- microVM/VM isolation;
- separate tenant hosts/accounts/projects;
- signed/pinned images and scanning;
- strict egress proxies;
- ephemeral credentials/workload identities.

Tiny-Agent deliberately calls its implementation a **baseline**.

A tutorial that says "Docker = perfectly safe sandbox" is easy to remember and wrong in interesting ways.

---

## 8. Threat-model examples

### Trusted internal script

```text
known code
no secrets
local dataset
```

A constrained container may be more than sufficient.

### Untrusted internet code

```text
arbitrary attacker-controlled code
sensitive host
multi-tenant service
```

Use a much stronger isolation design.

### Generated data-science code

```text
model-generated Python
private dataset
needs selected package repository/network
```

You may need ephemeral sandbox + controlled data mount + allowlisted egress + no orchestration credentials.

Same word "sandbox," very different threat models.

---

## 9. CI should execute the boundary

Tiny-Agent's CI performs a real constrained Docker smoke, not only a unit test that checks command strings.

Why both tests matter:

```text
unit test
-> flags/policy are constructed as expected

integration smoke
-> a real container can start under those restrictions
```

Security configuration that has never actually run is a particularly ambitious form of documentation.

---

## 10. What sandboxing does not solve

A sandbox does not automatically solve:

- prompt injection;
- Tool authorization;
- tenant ownership;
- malicious output/artifacts;
- data licensing/privacy;
- exactly-once side effects;
- correctness of generated code.

It constrains execution blast radius. Other stages own other layers.

---

## Core invariant

> **Execute open-ended/model-generated code with the minimum filesystem, network, credential, privilege, and resource authority needed for the task—and choose the isolation boundary from an explicit threat model.**
