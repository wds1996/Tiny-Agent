# 04 — Credentials, Network, Snapshots, Promotion, and Recovery

A good sandbox is not only about Linux flags. The architecture must also decide what credentials enter the environment, what network paths exist, what artifacts survive, and how work resumes after compute disappears.

A sandbox can be disposable. The user's work should not be accidentally disposable with it.

---

## 1. Keep orchestration credentials outside model-generated compute

The Agent service may have credentials for:

```text
model provider
job database
artifact store
MCP/A2A services
telemetry
```

A sandbox task often needs none of these.

Bad:

```text
web/Agent process environment
-> copy all environment variables into container
```

Better:

```text
harness keeps orchestration credentials
sandbox receives only task-scoped data/credentials
```

If the sandbox does not need a secret, the safest secret-injection mechanism is not injecting it.

---

## 2. Task-scoped credentials

When external access is required, prefer credentials with:

- minimal scope;
- short lifetime;
- specific tenant/project;
- restricted destination/action;
- revocation/audit where possible.

This is stronger than placing one permanent master API key in every analysis environment and asking generated code to behave professionally around it.

---

## 3. Network egress is a data-exfiltration channel

With unrestricted network, code can send workspace data anywhere reachable.

A mature policy asks:

```text
Does this task need network at all?
If yes, which hosts/services?
Which methods/protocols?
What request size/data classes?
Which credential?
Do we log/inspect egress?
```

Possible architectures:

```text
network none
allowlisted proxy
dedicated service Tool instead of raw network
separate download phase before sandbox execution
```

A narrow Tool often gives better control than arbitrary `curl`.

---

## 4. Download dependencies deliberately

Generated code may decide:

```text
pip install definitely-not-malware
```

Package installation adds:

- supply-chain risk;
- non-reproducibility;
- network egress;
- startup latency.

Better options include:

```text
prebuilt/pinned image
approved dependency manifest
internal package mirror
separate dependency-resolution policy
```

The fastest way to make an Agent environment unreproducible is to let it install "latest" everything whenever it feels inspired.

---

## 5. Snapshots vs durable artifacts

A compute snapshot captures environment state. An artifact captures a meaningful result.

```text
snapshot
    -> whole/partial runtime filesystem/environment state

artifact
    -> explicit output such as report, patch, dataset, log
```

Snapshots can speed rehydration but may accidentally capture secrets or stale state. Govern retention and contents carefully.

Long-horizon systems often benefit from explicit artifacts + reproducible environment manifests rather than treating opaque machine snapshots as the only source of truth.

---

## 6. Disposable compute, durable harness

Preferred relationship:

```text
TaskLedger / job state / ownership
           durable
             |
             v
sandbox compute instance
        disposable
             |
             v
workspace artifacts
           durable
```

If a container disappears:

```text
new worker reads ledger
-> mounts/loads workspace
-> reconstructs environment
-> continues task
```

Stage 10A implements this mental model with `TaskLedger` and `LongHorizonHarness`.

---

## 7. Promotion is a separate decision

Sandbox output should not automatically become user-facing production output.

Example:

```text
model edits code
-> sandbox tests
-> static/eval checks
-> optional human review
-> promote patch
```

Research:

```text
sandbox generates chart/data artifact
-> validate file/content
-> link provenance/evidence
-> include in final report
```

The sandbox is a workshop. The production artifact store is the showroom. Sawdust does not need to be promoted.

---

## 8. Recovery and side effects

A sandbox may crash after performing an external side effect but before the harness records success.

```text
external write succeeds
-> process dies
-> task appears incomplete
-> retry
```

This is the same ambiguity as Stage 07 retries and Stage 10 durable jobs.

Use:

- idempotency keys;
- transactional boundaries;
- downstream deduplication;
- explicit external operation records;
- human review for risky repeated actions.

Sandbox isolation does not create exactly-once semantics.

---

## 9. Worked long-running analysis

Task:

```text
Analyze 10 GB of experiment data and produce figures.
```

Architecture:

```text
service authenticates user/tenant
-> durable run queued
-> TaskLedger creates analysis subtasks
-> dataset mounted/read through governed workspace/object storage
-> sandbox gets no model-service master key
-> network disabled unless a specific dependency phase requires it
-> analysis writes figures/results
-> evaluator validates outputs
-> artifacts promoted
-> ledger persists completion
```

If compute dies halfway, the run identity and completed artifacts survive.

---

## 10. Completion checklist

For any Agent compute environment, answer:

```text
Which files can it read/write?
Which network destinations can it reach?
Which credentials can it see?
Which OS privileges/resources does it have?
What survives if it dies?
How is it reconstructed?
Which outputs are automatically trusted/promoted?
How are side effects made retry-safe?
```

If you cannot answer these, "we run it in a container" is not yet an architecture.
