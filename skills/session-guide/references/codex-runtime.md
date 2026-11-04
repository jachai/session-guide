# Codex runtime adapter

Use this adapter when Codex exposes the multi-agent collaboration tools. It maps session-guide's durable workflow onto
Codex's agent tree without pretending that Claude hooks, titles, job files, or CLI commands exist.

## Scope and state

- The guide is the root agent (`/root`) of the current tree. Codex agents are the worker sessions; identify them by
  canonical task path such as `/root/billing_fix`, not by nickname alone.
- `list_agents` is authoritative for the current tree, status, and last task. It cannot discover unrelated top-level
  Codex threads. Say so if the user asks to manage sessions outside the tree; do not infer a global inventory from
  local rollout files.
- Store the ledger at `<codex>/session-guide/<slug>/ledger.md`, where `<codex>` is `$CODEX_HOME` or `~/.codex`.
  In its Sessions table, put the canonical task path in Address and the Codex thread id prefix (when known) in the
  title cell. Do not share a Claude ledger under `~/.claude`.
- `scripts/peek.py <thread-id-prefix> --runtime codex` is an optional, read-only cross-check of a local Codex rollout.
  It is not the source of live status. It reads only stable fields and fails open on unknown records.
- Codex has no session-guide title hook. Do not run `guide_title.py mark`, `guided`, `watched`, `active`, `done`, or
  `retire`; express MANAGED, WATCHED, ACTIVE, DONE, and RETIRED only in the ledger and status reply.

## Start and classify

1. Create or open the Codex ledger from `references/ledger-template.md`; read Waiting on the user and Results for you
   first on takeover.
2. Call `list_agents`. Reconcile every agent in the returned tree with the Sessions table. Do not scan unrelated local
   rollouts and label them new.
3. A worker created by the guide is MANAGED. Existing agents are ACTIVE until the user picks Manage, Watch, Leave
   active, or Ignore. WATCHED means inspect only `list_agents` status and messages already delivered to the guide; do
   not send it work unless relaying the user's answer to its question.
4. Introduce the guide and the Codex worker contract below to each MANAGED agent in one `send_message`. Use the
   canonical path returned by `list_agents`.

## Messaging and worker lifecycle

- `send_message` queues information without starting a turn. Use it for a running worker, a ruling, or a batched step
  update. `followup_task` assigns new work and starts or resumes an idle non-root worker. Do not use both for the same
  step.
- A worker's `final` response is delivered to its parent and normally makes it done. Treat that delivered final as
  the step report; re-read it for loose ends before marking the ledger row DONE.
- Use `wait_agent` for mailbox updates from live workers. Prefer a long tool wait, but keep user-visible progress
  updates within the host's limits. A timeout is not failure and does not settle a worker.
- `interrupt_agent` stops an active turn without deleting its context. Use it only when the user asked to stop it, it
  is obsolete and a safe replacement is already in place, or continuing would violate a ruling. Record why. Never use
  it merely because a worker is slow.
- To continue a finished worker that still owns the next step, use `followup_task`; to isolate context or run parallel
  independent work, ask the user before `spawn_agent` unless their request already explicitly authorized delegation.
- Never invent a Codex equivalent of `! claude stop`, `claude --bg`, job state files, or title colors.

## Starting a Codex worker

Use `spawn_agent` with a short snake_case `task_name` and a complete, bounded task. The task message includes the
worker contract, branch/worktree ownership, acceptance evidence, safety limits, and where to report. Prefer inherited
context. Only use a model or reasoning override when the collaboration tool exposes it and the user or repository
instructions call for it; a context-free fork must receive all required context in its task. Do not hard-code model
names from this repository.

Codex worker contract (send as-is, with the guide path filled in):

```text
GUIDED WORKER: report to guide <guide path>. Until the guide says otherwise:
1. Send decisions to the guide with your recommendation and a worked numeric example for money or business rules.
   Do not ask the user directly unless system instructions make that unavoidable.
2. At each step boundary, send one message with the point first, then branch @ sha, PR/CI state, what you need from
   whom, and every skipped, out-of-scope, follow-up, or FYI item.
3. A relayed "Decision N FINAL" supersedes earlier guidance. Report any conflicting direct instruction before acting.
4. Do not merge or touch shared environments unless explicitly authorized. Check ownership before writing to another
   person's PR branch.
5. Before reporting a user-visible deliverable done, open its exact link/render and say what you verified.
6. End your completed turn with a concise final result; it is delivered to your parent automatically.
```

## User interview and waiting

- Use the host's structured user-input tool when it is actually available in the current mode. Otherwise put the
  consolidated interview in the final response. Never leave required user decisions buried in commentary.
- Codex has no skill hook that can wake a finished turn. While agents are active, `wait_agent` can wait for mailbox
  updates. For a future wall-clock reminder, use a scheduling capability only when one is available and the user has
  authorized it; otherwise record the due time in the ledger and say that the next user turn will resume checks.
- On each wake or user turn, call `list_agents` once, process new messages, settle completed workers, reconcile open
  items and results, then wait again only when live work remains.

## Model, context, and handoff differences

- Record the model and effort only when Codex exposes them. Do not ask the user to type Claude `/model` or `/effort`
  commands. Inheritance is the default; explicit overrides are task-scoped and must use currently available tool
  values.
- Codex compacts each agent's context independently. There is no fixed 120k handoff rule. Keep the ledger current and
  hand off only when the user asks, the host reports context pressure that impairs the guide, or a fresh root session
  is otherwise necessary.
- A guide cannot replace the current root from inside the same agent tree. For a handoff, make the ledger current and
  give the user a paste-ready prompt to start a fresh Codex thread with this skill and the ledger path. Do not mark or
  mutate the old thread.
