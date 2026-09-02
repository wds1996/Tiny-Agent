# Review questions

1. Distinguish harness, workspace, compute, container, and sandbox.
2. Why is `asyncio.to_thread()` not a sandbox?
3. Why does a filesystem read need authorization as much as a write?
4. What does `--network none` prevent and what does it not prevent?
5. Why keep orchestration credentials outside model-generated execution environments?
6. Design a policy for a research sandbox that may reach only Crossref and one internal document service.
7. When should a workspace file become a promoted artifact?
8. What state must survive if a container disappears halfway through a 3-hour task?
9. Which additional isolation would you add for hostile multi-tenant code?
10. Extend `DockerSandboxPolicy` with a controlled network profile without accepting arbitrary model-provided Docker flags.
