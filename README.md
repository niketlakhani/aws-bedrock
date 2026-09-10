# Patchwork — autonomous incident-response agent

A real error triggers an agent that diagnoses it, writes a fix, and opens a GitHub PR. The brain is a single [Strands](https://strandsagents.com) agent running on **Amazon Bedrock AgentCore** (Runtime + Memory).\
Test test

## How it works

```
buggy-service (Lambda)  ──throws──▶  CloudWatch logs  ──▶  Patchwork agent
                                                              │
                          diagnose → write fix → open PR ◀────┘
```

1. **buggy-service** runs and fails on bad input, logging a full traceback.
2. The **Patchwork agent** (Strands on AgentCore) picks up the error, inspects the offending source, and reasons about the root cause.
3. It writes a fix and opens a **GitHub pull request**.

## Components

### buggy-service (Lambda)

A small Python app with a real, diagnosable bug. See lambda/buggy_service/handler.py.

It computes a shipping quote for an incoming order. The bug: it assumes every order has a `customer.address`, but guest checkouts send `"customer": null`, so the handler raises `TypeError: 'NoneType' object is not subscriptable` and logs the traceback as structured JSON.

```bash
# Normal order → 200 with a quote
python -c 'from lambda.buggy_service.handler import handler; \
  print(handler({"id":"ord_42","customer":{"address":{"city":"London"}}}, None))'

# Guest checkout → raises, logs the traceback (the agent's input signal)
python -c 'from lambda.buggy_service.handler import handler; \
  handler({"id":"ord_43","customer":None}, None)'
```

The error log entry includes `errorType`, `message`, `source`, `function`, `stack`, and the offending `order` — everything the agent needs to trace the failure back to the source and propose a fix.

### Patchwork agent (Strands on AgentCore) — *planned*

The single agent that watches for errors, diagnoses them, writes a fix, and opens a PR. Not yet built; see [PLAN.md](PLAN.md).

## Project layout

```
lambda/
  buggy_service/
    handler.py        the buggy Lambda — throws on bad input, logs traceback
PLAN.md               the demo plan
```

## Roadmap

- [x] buggy-service Lambda that emits a real, diagnosable error

- [ ] Strands agent on AgentCore Runtime + Memory

- [ ] error → agent trigger (CloudWatch subscription / EventBridge)

- [ ] agent opens a GitHub PR with the fix
