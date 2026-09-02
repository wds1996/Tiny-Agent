# 04 — Model capabilities, reasoning, and model selection

An Agent architecture should not assume that every model has the same capability surface.

A provider may expose models that differ in:

- reasoning quality;
- context window;
- output limit;
- latency;
- input/output price;
- Function Calling quality;
- Structured Output support;
- image/audio/video support;
- built-in web/file/computer tools;
- fine-tuning or distillation options.

## Model capability vs runtime capability

A model may support Function Calling. That does not mean it can access your database.

A model may support computer use. That does not mean it is authorized to click your production console.

A model may support a million-token context. That does not mean your application should send a million tokens.

Keep this distinction:

```text
model capability
    = what inference/API can represent or propose

runtime capability
    = what your application actually exposes and permits
```

## Reasoning effort is a control knob, not magic

Reasoning-oriented APIs may let an application trade latency/cost for more inference effort.

Use more effort when task complexity and evaluation justify it. Do not automatically max reasoning for:

- deterministic routing;
- trivial extraction;
- fixed schema transformations;
- simple Tool selection.

The engineering loop is:

```text
candidate model/config
-> evaluation dataset
-> quality / latency / cost
-> choose the cheapest configuration that satisfies the product target
```

## Model routing

A mature system may route tasks among models, but model routing is still application policy.

Examples:

```text
simple classification -> small/fast model
complex research plan -> stronger reasoning model
embedding -> embedding model
speech -> realtime/audio model
```

Do not let a user string dynamically become an arbitrary provider model ID unless that is explicitly authorized product behavior.

## Provider details are versioned

Tiny-Agent isolates provider APIs behind adapters because model names, supported parameters, and response objects change faster than core Agent architecture.

Learn the invariant first:

> Select model capability through explicit application policy and verify the choice through evaluation, not intuition.
