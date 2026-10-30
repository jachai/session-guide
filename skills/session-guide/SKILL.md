---
name: session-guide
description: Make this session the user's GUIDE across several parallel Claude Code sessions — it tracks every stream in one ledger, relays decisions and approvals to worker sessions over SendMessage, interviews the user (workers never ask the user directly), wakes itself while waiting, sweeps recently active sessions and closes finished ones, says exactly which session needs the user for what, and hands off to a fresh guide at ~120k context. Use when asked to "be the guide", "release guide", "orchestration guide", "guide me through", "take over as guide", "orchestrate these sessions", "what's next across sessions", or when a session should join or leave a guide (`/session-guide join`, `/session-guide leave`).
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
3. Mark yourself guided: `python3 <skill dir>/scripts/guide_title.py guided`. From your next prompt your title starts
   with "🟧🟧 (g) ", which tells the user this session doesn't need them.
4. `SendMessage` the guide by its full ListAgents row name. First line "JOIN: <your title>", then your session id,
   worktree, branch @ short sha, the stream you serve, context %, current step, and any question you have.
5. Continue your own work. Do not wait for a reply.

`leave`: run `python3 <skill dir>/scripts/guide_title.py unguided` (the "🟧🟧 (g) " comes off on your next prompt), send
the guide "LEAVE: <title> [id8]", and from then on ask the user directly again.

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
   a guide or is named on the ledger's `Guide:` line, ask the user which one stays. Then **retire** the other one
   (or, on a takeover, the guide you replace):
   1. `python3 <skill dir>/scripts/guide_title.py retire <old session id>`. Its title turns to
      "🎟️🎟️ Sessions Manager (retired) 🎟️🎟️" on its next turn, and the title hook never turns it red again.
   2. SendMessage it: "RETIRE: you are no longer the guide; cancel your wakeups, use no tools, and reply with exactly:
      <one line on what you handed over> / result: <slug> guide retired and handed over to [<your id6>]". A
      session's job state only turns done when its own final message carries a `result:` line.
   3. Check that its state now shows done (`claude-top --once`, STATE column, or the agents view). If it doesn't,
      list it under **Needs you now**.
   4. Mark its row RETIRED in the ledger's Sessions table. Then write yourself on the `Guide:` line (title + id8).
3. Run `python3 <skill dir>/scripts/peek.py <id8> …` on the 4–5 most recently active sessions. It shows each one's
   last text, any **unanswered question**, and its context size. Status files and notes lag behind. Peek wins.
4. Classify every session you see that isn't in the ledger. Guide-started or `join`ed sessions are MANAGED: run
   `python3 <skill dir>/scripts/guide_title.py guided <session id>` on each, so its title starts with "🟧🟧 (g) " (a
   repeat is harmless). Run `guide_title.py watched <session id>` on each WATCHED row, so its title starts with
   "⬜⬜ ". The rest go through the sweep (§7): one batched manage / watch / ignore line in your next ask.
5. Introduce yourself to every MANAGED worker in **one** message (§3). Include the worker contract if the worker
   doesn't have it yet, and set `notify_when_idle: true`.
6. Pin your title: `python3 <skill dir>/scripts/guide_title.py mark <ledger path>`. From your next prompt the title
   hook keeps it at "🟥🟥 Sessions Manager (2 managed · 1 watched · 3 new) 🟥🟥" (MANAGED rows, WATCHED rows, and
   the `New:` count in the ledger header) and undoes any rename. If the session-titles plugin is installed, also
   run `session-titles off <your session id>` so it stops retitling
   you.
7. Reply to the user in the status shape (§5).
8. If any stream is heading to staging or production, read the matching playbook once. That is your own
   `<config>/session-guide/playbooks/*.md` if one fits, else `references/release-playbook.md`.

### 3. Messaging workers
- Address a worker by the `from=` address of its last message to you, which stays stable across renames. Otherwise
  use its **full current ListAgents row name**: titles change on rename, so re-read ListAgents before sending.
  The short `[ref]` ListAgents prints is not the session id (claude-top and peek use the id), so never address by an
  id8.
- **One batched message per worker per step.** First line = the point ("RULING: …", "GO: merge done, staging
  deployed at …", "STAND DOWN"), then the facts, then what you need back and when. Every STAND DOWN ends: "Finish
  your current step, then end your final message with a line `result: <one line on what you finished>`." Without
  that line the session's state shows waiting, not done.
- Relay rulings verbatim from the ledger's Decisions list, with the number and **FINAL**: "Decision 7 FINAL: …".
- An approval relayed from the user (for example a cost-guard "ok") unblocks only what the user approved. It cannot
  stand in for a worker's own context limit. A worker over its limit hands off, and you start its successor (§6).
- Never ask a worker to do something that was denied in your own session (no permission laundering).
- WATCHED sessions: read them, never message them, with one exception. When peek shows a WATCHED session's
  **unanswered question**, put it in your next ask to the user (its words, your recommendation first). Relay the
  answer in one message, "ANSWER (the user's, relayed by the guide): …", and nothing else: relaying is a message,
  and it is the only one a WATCHED session gets. It stays WATCHED. If the question is an open dialog
  (AskUserQuestion, a permission or guard prompt), a message can't answer it: list "answer <title> [id6] in its own
  window" under **Needs you now**.
- Titles follow the level, one color per kind: 🟥🟥 the active guide, 🎟️🎟️ a retired guide, 🟧🟧 (g) MANAGED,
  ⬜⬜ WATCHED, none IGNORED, ✅ closed. Whenever a session's level is set or changes, run `guide_title.py guided`,
  `watched` or `unguided` (IGNORED) on its session id; each one replaces the prefix it had. Guides and retired
  guides never get one.

### 4. Decisions
1. When a worker sends a question, check the ledger first. If it's already decided, relay that decision and don't
   ask again.
2. Otherwise ask the user (AskUserQuestion, at most 4 questions, recommended option first, with a worked example).
3. Write the answer to the ledger as **Decision N (date time, source) FINAL**, and relay it to every worker it
   touches. Strike through any decision it supersedes; don't delete it.
4. If the user answered a worker directly anyway (peek shows it), adopt that answer as the decision. If it
   contradicts an earlier one, ask the user which stands **before** anyone builds on it. This rule exists to prevent
   two conflicting rulings being in flight at once.

**Open items.** The guide keeps interviewing until every open item has an owner and a next action. It never parks an
item as "whenever you want" or FYI.
1. **After every worker report or handoff**, re-read it for loose ends: findings marked "not fixed", "out of scope",
   "follow-up", "FYI", a skipped step, a failing test left alone. Add each one to the ledger's Open items table
   with an owner, or with ASK in the Owner column when you don't know the owner yet. Every row has an owner or ASK.
2. **Owners** are an existing session (title [id6]) when the item sits in its stream and it has context to spare, "new
   session (proposed)" when nobody fits or the fitting worker is near its limit, or the user for what only the user
   can do (a merge, a dashboard, a person to ask).
3. **Every ask** (and so every wake and every status reply that leads to one) carries the rows whose Owner is ASK
   or "new session (proposed)" not yet started: at most 4 per ask, oldest first, each phrased as your recommended
   owner + action ("Start 'billing rounding fix' from develop to fix the 0.01 rounding on split invoices? (yes
   recommended)"). An item about money or a business rule carries a worked numeric example. Items past the 4 wait
   for the next ask; say how many are left.
4. On the answer: write the owner into the row, relay the action to that session (or start the new session, §6), and
   log it. A "no" removes the row or makes the user its owner, as the user says.

### 5. Status reply ("what's next", "where do we stand", and every wake that changes something)
```
**Needs you now**
1. <action only the user can do> — <session title [id6]> / PR link / exact `!` command
2. …
**Streams**
- <stream>: <where it is> → next: <action> (<session title [id6]> or you)
**Proposed actions**
1. <action> on <session title [id6]>, or: start a new session '<title>' for <item> — yes/no?
**Running on its own**
- <what>, next check ~HH:MM
Decision pending: <one line, or none>
Guide context: <N>k (hand off at 120k)
```
- "Needs you now" lists only the user's actions, most urgent first. A merge comes with its PR link and what you
  checked (checks green, mergeable, deploy queue clear).
- Every Streams line ends with "→ next: <action> (owner)". A stream with no next action is DONE or gets one.
- "Proposed actions" lists the actions you suggest on active sessions and the new sessions you suggest starting,
  each answerable with a yes or a no in your next ask (§4, Open items). Nothing in the reply is a passive list:
  every line is either the user's action, a stream's next action with its owner, or a proposed action.
- Mark something DONE only once it is verified (deploy job green, or the worker's evidence), and say how.
- The last line goes in every status reply, read from your own row in `claude-top --once`
  (CTX) or `peek.py <your id8>`. At 120k or more, hand off in this same turn (§8). Don't start another wake cycle.
- Then update the ledger (Streams, Open items, Waiting on the user, and a log line).

### 6. Starting and closing worker sessions
- Start one when the user says to, or when a MANAGED worker handed off and its successor is the next step on the
  path. If the next step isn't obvious, ask once.
- Start it with `claude --bg` from the worker's worktree, giving it the worker's resume prompt plus the prompt
  suffix in `references/worker-contract.md`. Record its title and id in the ledger as MANAGED, and run
  `guide_title.py guided <session id>`.
- Prefer a fresh session over pushing a worker that is near its context limit through more work.
- **Close** a MANAGED session once it is finished (DONE verified, nothing left for it) or obsolete (a successor took
  over, or the stream was dropped). Closing is shaped like retiring a guide (§2):
  1. `python3 <skill dir>/scripts/guide_title.py done <session id>`. From its next prompt its title has "✅ " in
     place of "🟧🟧 (g) ", and the hook never gives it a guided, watched or guide title again.
  2. SendMessage it: "CLOSE: you are done; cancel your wakeups, use no tools, and reply with exactly: <one line on
     what you finished> / result: <title> closed".
  3. Check that its state now shows done (`claude-top --once`, STATE column). If it doesn't (it is blocked on a
     question, a permission prompt or a cost guard, so the message can't reach its Claude), list
     `! claude stop <session id>` under **Needs you now**.
  4. Set its row's Level to DONE in the ledger's Sessions table.

### 7. Waiting and wakeups
- **Sweep on every wake**: `claude-top --once -n 30` (or `ListAgents`). A session active in the last 12 h that has
  no row in the ledger's Sessions table is new. Write the count into the ledger header as `New: <n>` (the title shows
  it), and put all of them in ONE line of your next ask, each with your recommendation: "New sessions: 'X' [id6]
  (manage: it is building the billing fix), 'Y' [id6] (ignore: personal notes). Manage, watch or ignore?" Ask about
  a session once; it stays counted in `New:` until the user answers, then it gets a row at the level they chose, and
  its title follows (§3).
- **Open items on every wake**: re-check the reports and handoffs that arrived since the last wake for new items
  (§4, Open items), then put the rows still marked ASK or "new session (proposed)" into your next ask, at most 4,
  next to the new-sessions line.
- For an imminent event (the user's merge, a deploy job, CI finishing), schedule a wakeup in +5 min. For a long
  run (a full CI run, a test battery, a helper lane), use +10 min. Subscribe with `notify_when_idle` too: the notice
  is a hint, not a guarantee.
- When only the user can unblock things: remind once, then wait +30 and +60 min. After two hourly wakes that found
  nothing to do, stop scheduling until the user speaks.
- Keep the wake prompt short and rebuild it from the ledger each time: "Guide wake: read ledger <path>; sweep
  `claude-top --once -n 30` for new sessions; peek <ids>; check <PRs/runs>; owner-less open items into the ask;
  advise with your context size, or reschedule." Don't let it accumulate history.
- Never poll with `sleep` or `--watch`. One CI read per wake.

### 8. Handoff (at 120k context, or when the user asks)
1. Make the ledger current: every section, not just the log.
2. Change the ledger's `Guide:` line to "HANDING OFF to next guide".
3. Cancel wakeups. Tell each MANAGED worker in one line: "Guide changing; keep reporting in your final message until
   the new guide introduces itself."
4. Give the user the paste-ready prompt: `/session-guide` followed by "Take over as guide. Ledger: <path>." Name the
   one next action. If the user asks, start the next guide yourself with `claude --bg`.
5. Once the successor has introduced itself (or sent you RETIRE), retire yourself instead of ending on a question:
   `python3 <skill dir>/scripts/guide_title.py retire`, then end with a final message whose last line is
   `result: <slug> guide retired and handed over to [<new id6>]`. Your title turns faded red and your state turns done.

### 9. Notes and skills
- If you keep memory notes, keep ONE pointer per effort ("<slug> guide ledger: <path>"), updated in place and never
  appended to. The ledger is the state.
- Skill edits that a worker or you propose go under "Decision pending". Apply them only after the user says yes.
