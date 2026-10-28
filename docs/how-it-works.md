# How it works

## Roles

```mermaid
flowchart LR
    U([You]) <-- "one interview,<br/>'Needs you now'" --> G[Guide session]
    G -- "Decision N FINAL,<br/>GO / STAND DOWN" --> W1[Worker: billing lead]
    G -- relays --> W2[Worker: reindex]
    W1 -- "step reports,<br/>questions" --> G
    W2 -- "step reports,<br/>questions" --> G
    G -. reads only .-> W3[Watched session]
    G <--> L[(ledger.md)]
    G -. "gh: checks, runs, deploys" .-> CI[(CI / deploys)]
```

The guide never builds and never merges. Workers build. You decide and merge.

## A guide's turn

1. **Read the ledger.** It is the only state. Notes and status files are hints at best.
2. **Peek** at the 4–5 most active sessions (`peek.py`): last reply, any unanswered question, context size.
3. **Read CI**: PR checks, workflow runs, deploy jobs. One read per wake, never a watch loop.
4. **Reconcile.** Answer workers' questions from the Decisions list where possible. Batch the rest into one
   interview with you. Write the answers as numbered FINAL decisions and relay them, one message per worker.
5. **Reply** to you in the "Needs you now / Streams / Running on its own / Decision pending" shape.
6. **Update the ledger** in place and schedule the next wake: +5 for imminent events, +10 for long runs, backing off
   when only you can unblock things.

## Decisions

A decision is written once and relayed verbatim. If you contradict an earlier decision, the old line is struck
through, not deleted, so a fresh guide can see what changed. When you answer a worker directly, the guide adopts the
answer, and asks you which ruling stands if it conflicts with an earlier one, before anyone builds on it.

## Handoffs

Workers hand off near their context limit with a resume prompt. The guide starts the successor and records it as
MANAGED. The guide itself hands off at ~120k: because the ledger is current, the next guide needs one line,
`/session-guide` + "Take over as guide. Ledger: <path>."

The guide it replaces is **retired**, not left hanging. The new guide runs `guide_title.py retire <old id>`, so the old
title turns to "🟩🟩 Sessions Manager (retired) 🟩🟩" and never goes red again. Then it asks the old guide for a
final message ending in a `result:` line, which turns that session's state to done instead of "needs input". It
checks the state, and marks the old guide's row RETIRED in the ledger. An outgoing guide that sees its successor
introduce itself retires itself the same way.

## Addressing sessions

Session titles change when sessions rename themselves. The guide replies to a worker's `from=` address when it has
one. Otherwise it re-reads `ListAgents` and uses the full current row name. Talking to you, it always uses the
title, with the short id in brackets.
