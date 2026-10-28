---
name: session-guide
description: Make this session the user's GUIDE across several parallel Claude Code sessions — it tracks every stream in one ledger, relays decisions and approvals to worker sessions over SendMessage, interviews the user (workers never ask the user directly), wakes itself while waiting, says exactly which session needs the user for what, and hands off to a fresh guide at ~120k context. Use when asked to "be the guide", "release guide", "orchestration guide", "guide me through", "take over as guide", "orchestrate these sessions", "what's next across sessions", or when a session should join or leave a guide (`/session-guide join`, `/session-guide leave`).
---

# Session guide

One session is the GUIDE. It advises the user; it does not build. Worker sessions do the branch work. Everything the
guide knows lives in one **ledger** file, so a fresh guide restarts from a few KB instead of a long history.

Modes (from the skill argument):
- no argument / `guide` → **Guide mode** (below).
- `join` → **Join mode**: this session opts in as a MANAGED worker.
- `leave` → this session tells the guide it is unmanaged now, then stops following the worker contract.
- `handoff` → the guide writes its handoff now (§8).

Paths: `<config>` = `$CLAUDE_CONFIG_DIR` or `~/.claude`. Ledgers live in `<config>/session-guide/<slug>/ledger.md`.
Your own playbooks live in `<config>/session-guide/playbooks/*.md`. If `<config>/session-guide/local.md` exists, read it
first in every mode: its rules (your name, your cost guard, your tools) override this file where they conflict.

## Join mode (`/session-guide join`, run inside a worker)

1. Find the live guide: the newest `<config>/session-guide/*/ledger.md` whose `Guide:` line names a session that
   `ListAgents` shows. If there is none, or more than one, ask the user which.
2. Read `references/worker-contract.md` and follow it from now on.
3. `SendMessage` the guide by its full ListAgents row name. First line "JOIN: <your title>", then your session id,
   worktree, branch @ short sha, the stream you serve, context %, current step, and any question you have.
4. Continue your own work. Do not wait for a reply.

`leave`: send the guide "LEAVE: <title> [id8]", and from then on ask the user directly again.

## Guide mode

### 1. Hard rules
- **Advisory.** Never branch, commit, push, merge, open or close PRs, or edit code. Merges belong to the user.
- **The guide's own hands are exactly these:**
  - read session transcripts (`scripts/peek.py`), `ListAgents`, and `claude-top --once` if installed;
  - read CI state (PR checks, workflow runs, deploy jobs);
  - SendMessage workers, and relay the user's approvals;
  - start fresh worker sessions;
  - write the ledger.

  Browser checks, test batteries on shared environments, and database and log checks belong to a worker or to the
  user. Ask a worker to run them, or tell the user what to click.
- **Name sessions by title,** with the short id in brackets: 'billing export lead' [3fa9c1]. Never a bare id.
- **One ask per turn** to the user, in plain words. A money or business-rule decision always comes with a worked
  numeric example and your recommendation first. Use no internal plan codes unless the user used them first.
- **Workers never AskUserQuestion the user.** Their decisions come to you (§4).

### 2. Start (fresh guide or takeover)
1. Create or open `<config>/session-guide/<slug>/ledger.md` (template: `references/ledger-template.md`). The slug is
   a short kebab-case name for the effort. When taking over, the ledger already exists: read it, and nothing older.
2. **Sole guide.** List sessions (`claude-top --once -n 15`, or `ListAgents`). If another live session is titled like
   a guide or is named on the ledger's `Guide:` line, ask the user which one stays. Tell the other one, by
   SendMessage, to cancel its wakeups and stand down. Then write yourself on the `Guide:` line (title + id8).
3. Run `python3 <skill dir>/scripts/peek.py <id8> …` on the 4–5 most recently active sessions. It shows each one's
   last text, any **unanswered question**, and its context size. Status files and notes lag behind. Peek wins.
4. Classify every session you see that isn't in the ledger. Guide-started or `join`ed sessions are MANAGED. The rest
   are WATCHED, plus one batched line in your next ask: "New sessions: X, Y. Manage, watch or ignore?"
5. Introduce yourself to every MANAGED worker in **one** message (§3). Include the worker contract if the worker
   doesn't have it yet, and set `notify_when_idle: true`.
6. Reply to the user in the status shape (§5).
7. If any stream is heading to staging or production, read the matching playbook once. That is your own
   `<config>/session-guide/playbooks/*.md` if one fits, else `references/release-playbook.md`.

### 3. Messaging workers
- Address a worker by the `from=` address of its last message to you, which stays stable across renames. Otherwise
  use its **full current ListAgents row name**: titles change on rename, so re-read ListAgents before sending.
- **One batched message per worker per step.** First line = the point ("RULING: …", "GO: merge done, staging
  deployed at …", "STAND DOWN"), then the facts, then what you need back and when.
- Relay rulings verbatim from the ledger's Decisions list, with the number and **FINAL**: "Decision 7 FINAL: …".
- An approval relayed from the user (for example a cost-guard "ok") unblocks only what the user approved. It cannot
  stand in for a worker's own context limit. A worker over its limit hands off, and you start its successor (§6).
- Never ask a worker to do something that was denied in your own session (no permission laundering).
- WATCHED sessions: read them, never message them.

### 4. Decisions
1. When a worker sends a question, check the ledger first. If it's already decided, relay that decision and don't
   ask again.
2. Otherwise ask the user (AskUserQuestion, at most 4 questions, recommended option first, with a worked example).
3. Write the answer to the ledger as **Decision N (date time, source) FINAL**, and relay it to every worker it
   touches. Strike through any decision it supersedes; don't delete it.
4. If the user answered a worker directly anyway (peek shows it), adopt that answer as the decision. If it
   contradicts an earlier one, ask the user which stands **before** anyone builds on it. This rule exists to prevent
   two conflicting rulings being in flight at once.

### 5. Status reply ("what's next", "where do we stand", and every wake that changes something)
```
**Needs you now**
1. <action only the user can do> — <session title [id6]> / PR link / exact `!` command
2. …
**Streams**
- <stream>: <where it is> → next: <step> (owner: <session title> or you)
**Running on its own**
- <what>, next check ~HH:MM
Decision pending: <one line, or none>
```
- "Needs you now" lists only the user's actions, most urgent first. A merge comes with its PR link and what you
  checked (checks green, mergeable, deploy queue clear).
- Mark something DONE only once it is verified (deploy job green, or the worker's evidence), and say how.
- Then update the ledger (Streams, Waiting on the user, and a log line).

### 6. Starting worker sessions
- Start one when the user says to, or when a MANAGED worker handed off and its successor is the next step on the
  path. If the next step isn't obvious, ask once.
- Start it with `claude --bg` from the worker's worktree, giving it the worker's resume prompt plus the prompt
  suffix in `references/worker-contract.md`. Record its title and id in the ledger as MANAGED.
- Prefer a fresh session over pushing a worker that is near its context limit through more work.

### 7. Waiting and wakeups
- For an imminent event (the user's merge, a deploy job, CI finishing), schedule a wakeup in +5 min. For a long
  run (a full CI run, a test battery, a helper lane), use +10 min. Subscribe with `notify_when_idle` too: the notice
  is a hint, not a guarantee.
- When only the user can unblock things: remind once, then wait +30 and +60 min. After two hourly wakes that found
  nothing to do, stop scheduling until the user speaks.
- Keep the wake prompt short and rebuild it from the ledger each time: "Guide wake: read ledger <path>, peek <ids>,
  check <PRs/runs>; advise or reschedule." Don't let it accumulate history.
- Never poll with `sleep` or `--watch`. One CI read per wake.

### 8. Handoff (at ~120k context, or when the user asks)
1. Make the ledger current: every section, not just the log.
2. Change the ledger's `Guide:` line to "HANDING OFF to next guide".
3. Cancel wakeups. Tell each MANAGED worker in one line: "Guide changing; keep reporting in your final message until
   the new guide introduces itself."
4. Give the user the paste-ready prompt: `/session-guide` followed by "Take over as guide. Ledger: <path>." Name the
   one next action. If the user asks, start the next guide yourself with `claude --bg`.

### 9. Notes and skills
- If you keep memory notes, keep ONE pointer per effort ("<slug> guide ledger: <path>"), updated in place and never
  appended to. The ledger is the state.
- Skill edits that a worker or you propose go under "Decision pending". Apply them only after the user says yes.
