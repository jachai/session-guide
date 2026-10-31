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
   Every loose end a report raised ("not fixed", "out of scope", "FYI") becomes an Open items row with an owner;
   rows without one go into the same interview as a recommended owner + action, at most 4 at a time.
5. **Reply** to you in the "Needs you now / Streams / Proposed actions / Running on its own / Decision pending"
   shape. Every stream line ends with its next action and owner; every proposed action is a yes/no.
6. **Update the ledger** in place and schedule the next wake: +5 for imminent events, +10 for long runs, backing off
   when only you can unblock things.

## Decisions

A decision is written once and relayed verbatim. If you contradict an earlier decision, the old line is struck
through, not deleted, so a fresh guide can see what changed. When you answer a worker directly, the guide adopts the
answer, and asks you which ruling stands if it conflicts with an earlier one, before anyone builds on it.

## Handoffs

Workers hand off near their context limit with a resume prompt. The guide starts the successor and records it as
MANAGED. The guide itself prints its context size in every status reply and hands off at 120k: because the ledger
is current, the next guide needs one line, `/session-guide` + "Take over as guide. Ledger: <path>."

The guide it replaces is **retired**, not left hanging. The new guide runs `guide_title.py retire <old id>`, so the old
title turns to "🎟️🎟️ Sessions Manager (retired) 🎟️🎟️" and never goes red again. Then it asks the old guide for a
final message ending in a `result:` line, which turns that session's state to done instead of "needs input". It
checks the state, and marks the old guide's row RETIRED in the ledger. An outgoing guide that sees its successor
introduce itself retires itself the same way.

## Guided prefix

A MANAGED worker's title starts with "🟧🟧 (g) ", so the user can see which sessions don't need them. The marker is a
file next to the guide's own (`guides/<session id>`, holding `guided`), written by `guide_title.py guided`. On each
prompt the hook reads the session's current title and, when the prefix is missing, sets the same title with it in
front. When the prefix is already there it prints nothing, so a titling hook's focus update goes through untouched;
session-titles' answer overrides this hook's, so the prefix also goes into its stored origin, whenever a marker is
written and on every prompt. `unguided` flips the marker
to `unguided`: the hook strips the prefix on the next prompt, then deletes the marker. Guide and retired markers hold
a ledger path or `retired`, so they never get the prefix.

A WATCHED session works the same way with the marker `watched` and the prefix "⬜⬜ " (`guide_title.py watched`), so
a light gray row is a session the guide only reads. An ACTIVE session has the marker `active` and the prefix "🟦🟦 ":
running, but the guide neither reads nor messages it. Anything else that reads these markers must treat a keyword it
doesn't know as "not a guide": only a path is a guide.

## Sweeps and closing

On every prompt the guide gets, the title hook runs a sweep (`guide_title.py sweep`), reading transcripts directly. A
session active in the last 12 hours with no row in the ledger is new: the title shows the live count, and the list
goes to the guide with each prompt until every session on it has a row. That list can't drift and needs no other
tool. The guide keeps a wake scheduled while any session is active, because nothing wakes it when a session starts.

Everything the guide needs from you goes through `AskUserQuestion`, not text: new sessions (Manage / Watch / Leave
active / Ignore), decisions, approvals it can relay, and Done / Not yet for what only you can do. A WATCHED session that asks a question gets it put to the user, and the
answer relayed back in one message, its only one.

A MANAGED session that is finished or obsolete is closed, the way a guide is retired: `guide_title.py done <id>`
writes the marker `done`, so the hook swaps "🟧🟧 (g) " for "✅ " and never gives the session a guided, watched or guide title
again. The guide asks it for a final message with a `result:` line, checks its state shows done, and marks its row
DONE. A session stuck on a dialog can't read the message, so the user gets `! claude stop <id>` instead.

## Addressing sessions

Session titles change when sessions rename themselves. The guide replies to a worker's `from=` address when it has
one. Otherwise it re-reads `ListAgents` and uses the full current row name. Talking to you, it always uses the
title, with the short id in brackets.
