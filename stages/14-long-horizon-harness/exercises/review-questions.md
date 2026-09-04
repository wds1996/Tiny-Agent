# Review questions

1. Why is a long transcript not a durable task ledger?
2. Which facts belong in exact structured state instead of a compact handoff summary?
3. What should a worker persist before its context window ends?
4. Distinguish retry, repair, and replan with examples.
5. Why is sandbox loss recoverable only when harness/workspace state is externalized?
6. Design a run that lasts six hours and survives three worker restarts.
7. Where would human approval enter a long-horizon workflow with external side effects?
8. How would you prevent two workers from owning the same service job simultaneously?
9. Which evals should run after every task vs only before final completion?
10. Extend the teaching TaskLedger with blocked/cancelled states and explain the new transitions.
