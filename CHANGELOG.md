# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Codex multi-agent support through a runtime adapter that maps the guide workflow to Codex's native agent tree and
  collaboration actions without invoking Claude hooks, titles, job files, or CLI commands. Codex ledgers live under
  `$CODEX_HOME/session-guide`, and the adapter explicitly limits management to the current tree.
- `peek.py --runtime codex` reads local Codex rollout metadata, model/effort, context usage, assistant replies,
  structured questions, and inbound agent messages. Auto mode can resolve Claude or Codex transcripts.
- `install.sh --codex` installs or links the skill under `$CODEX_HOME/skills`; uninstall keeps ledgers.

## [0.1.15] - 2026-11-03

### Added

- **Not your PR, not your branch.** Before the guide sends any session to write to a PR's branch (merge another branch
  in, fix a conflict, push a fix, revert), it checks the PR's author and assignee with
  `gh pr view N --json author,assignees,headRefName,body`. If the PR isn't the user's own, it asks first in the
  interview, naming the owner ("PR #N is Max's (branch X); let a session push to his branch?"). A user ruling that
  names the PR in a merge order does not count as that permission. Worker prompts that touch a PR branch carry the
  owner check result, and the worker contract (rule 10) tells workers to stop and ask when it is missing. Why: a
  conflict-fix session was sent to a PR from a merge order without the check; it was a teammate's PR and our merge
  commit landed on their branch and had to be reverted.

## [0.1.14] - 2026-11-03

### Added

- **Results for you.** A finished deliverable the user asked for (a doc, a deck or slide, a review, a report, a
  release, a PR ready for them) is recorded with `guide_title.py result "<deliverable>" <link> --from "<title [id6]>"`
  in the ledger's new Results for you table (deliverable, link, delivered, asked, answer), listed under a new
  **Results for you** status heading between Needs you now and Streams, and asked about in the interview: Satisfied /
  Change it / Drop it / Haven't looked yet. `result-answer "<deliverable>" satisfied|change|drop|not-looked` records
  the verdict; not-looked is asked again on the cadence the user picks (`--every <hours>`, default 1). `settle` and the
  hook list unanswered results like due reminders. The stream is not DONE, and its loose ends stay open, until the user
  answers; the worker session may close, the row stays.
- **Look before done.** Before a worker reports a user-visible deliverable as done, it opens it the way the user will
  (rendered, at the exact link) and confirms the change shows; the worker contract (rule 9) and SKILL §3 say so. A
  report without that is "delivered, unchecked": the guide sends a CHECK before presenting it, and the DONE rule in §5
  needs both that look and the user's Satisfied.
- **Owed questions survive handoffs.** `guide_title.py waiting ask "<question>" --hours N` (or `--at "YYYY-MM-DD HH:MM"`)
  writes a dated "owed question [<key>]" row in the waiting table the moment the guide says it owes the user a
  question, so a successor's `settle` surfaces it; `sleep <key>` and `unwait <key>` move or clear it. The takeover
  steps read the waiting and results tables first, and the handoff step requires every owed question to be a row.
- Status replies lead with what finished since the last reply, each with its link, before the stream list.

## [0.1.13] - 2026-11-03

### Added

- The guide picks the model and effort for each session it starts. `references/model-choice.md` is a short table keyed on
  the task the session does next, with the cost reason for each row: money and business-rule fixes, migrations, release
  gates and design reviews get the top model at high effort; well-specified builds the top model at medium; verify
  follow-ups `sonnet` at medium; mechanical edits, CI reads, read-only data checks and status reports `sonnet` at low.
  The guide starts sessions with `claude --bg --model <alias> --effort <level>`, using aliases so the table stays
  current; `local.md` can name a different top model.
- On a takeover, and when the user picks Manage or Watch for a session, the guide reads its model and effort and, when
  they don't fit its task, asks the user to type `/model <alias>` and `/effort <level>` in its window (the guide can't
  switch another session). "Keep as is" is recorded, so it isn't asked again until the task changes.
- A worker's successor is picked again for the next step's task, not copied from its predecessor.
- The ledger's Sessions table has a Model / effort column.
- `peek.py` shows the model and effort of a session's last main-thread turn on its first line.

## [0.1.12] - 2026-11-03

### Added

- Follow-up verification of recent fixes and deployments. About once a day (`SESSION_GUIDE_FOLLOWUP_HOURS`, default 24,
  0 = off) the hook tells the guide a review is due. `guide_title.py followups` lists the PRs and versions that the
  ledger's last 3 days or the sessions' transcript reports say reached production, staging, a merge or a release, with
  no verification recorded; the guide weeds the list and proposes a read-only "verify <thing>" session for each through
  the Open items flow. `guide_title.py verification <thing> <result> "<evidence>"` records proposed, running, verified,
  not-exercised (listed again for a re-check after 24 hours), broken or skipped in the ledger's new Verifications table.
- `references/verify-followup.md`: the brief for that read-only session. It reviews the merged code and the intended
  behaviour, states the expected behaviour in concrete terms (numbers where money is involved), checks real data and
  logs since the deploy, and reports verified, not exercised yet or broken, with evidence and loose ends. Database and
  log tools are named by role, so `local.md` can name the real ones.

## [0.1.11] - 2026-11-02

### Added

- Every MANAGED or WATCHED session now has to settle as waiting on the user or done, so nothing the guide followed is
  forgotten. `guide_title.py settle` lists sessions quiet for 2 hours in neither state, and reminders that are due; the hook
  gives a guide both on every prompt. `waiting` records the exact action in the ledger's waiting table, `sleep` puts the
  reminder off (the guide offers 1, 2, 8, 12, 24 and 48 hours), `unwait` removes it, and `done` removes it too.

### Changed

- With no active session, the guide no longer stops waking while reminders exist: it keeps one one-shot cron at the next
  reminder, since a wakeup can't reach past 60 minutes.

## [0.1.10] - 2026-11-02

### Fixed

- Closed sessions could stay orange for good. `done` tried the rename once: a session whose process was still running
  (they linger for hours after finishing) was skipped with nothing to retry it, and sessions closed before 0.1.9 were
  never revisited, because the "Closable" list skips anything already marked `done`. Every guide prompt and every
  `sweep` now renames closed sessions whose process has ended, and tell the guide to send CLOSE to those a process
  still holds.

## [0.1.9] - 2026-11-02

### Fixed

- A closed session kept its orange "🟧🟧 (g)" name in `claude agents` and claude-top. `done` only changed the marker and
  session-titles' stored origin, and the name the agents view shows (the job's `state.json` `name`) changes only when
  the session's next prompt runs the hook, which a finished session never gets. `done` now writes the "✅ " name
  itself when no process holds the session. Claude Code has no command that renames a session without running a turn
  in it, so this one-key edit is the only route for a session that is over; a live session is left alone and changes on
  its next prompt, as before. If it resumes later, the hook follows its `done` marker.
- The sweep (and the guide's hook context) lists sessions that are still marked managed, watched or active although
  every ledger row naming them is DONE, and says to run `done` on them. A job state of done alone never closes a
  session: workers' state goes done at every final message and the guide can resume them.

## [0.1.8] - 2026-11-02

### Fixed

- The guide's title no longer counts sessions that are closed: a row whose session has a `done` marker is skipped, and
  a session named by several rows counts once, at its topmost row's Level (rows with no `[id]` count as before). A
  title could show "33 managed" with nothing running.
- `guide_title.py done <id>` now also sets that session's Level to DONE in the guide's ledger, or says it couldn't
  find the ledger and closes anyway.

## [0.1.7] - 2026-10-31

### Added

- An ACTIVE level for sessions that are running but neither managed nor watched: `guide_title.py active <id>` puts
  blue blocks, "🟦🟦 ", before the title (override: `SESSION_GUIDE_ACTIVE_PREFIX`). The guide's title counts them.
- `guide_title.py sweep`: lists recently active sessions with no ledger row, reading transcripts directly, so it
  needs neither claude-top nor ListAgents. `claude -p` runs are left out.

### Changed

- The guide interviews. Anything it needs from you ends its turn in `AskUserQuestion`: new sessions, decisions,
  approvals it can relay, and Done / Not yet for what only you can do. Text is the fallback only when the tool is
  refused or unavailable, and an unanswered question is asked again.
- The title hook gives the guide the list of new sessions on every prompt, until each has a row, instead of relying on
  a sweep at wake time. The title's `new` count is live, so the ledger's `New:` line is gone.
- The guide keeps a wake scheduled while any session was active in the last 2 h, instead of stopping after two idle
  hourly wakes. It falls back to `CronCreate` when `ScheduleWakeup` is unavailable.
- In `SESSION_GUIDE_TITLE`, `{active}` now counts ACTIVE rows. Use the new `{tracked}` for what it used to mean,
  managed + watched.

## [0.1.6] - 2026-10-30

### Fixed

- The guided, watched and closed prefixes now show up on sessions running the session-titles plugin. Its hook's title
  overrode this one on most prompts, so the prefix only appeared when it had nothing to say. `guide_title.py` now
  writes the prefix into its stored origin, so both hooks give the same title.
- Marking or retiring a guide turns session-titles off for that session, so nothing overrides its red or faded red
  title.

## [0.1.5] - 2026-10-30

### Added

- WATCHED sessions get a title too: `guide_title.py watched <id>` puts light gray blocks, "⬜⬜ ", before the title
  (override: `SESSION_GUIDE_WATCHED_PREFIX`). `unwatched` takes them off, and `guided` and `watched` swap one prefix
  for the other. The guide runs these whenever a session's level is set or changes.

### Changed

- One color per kind of session. MANAGED sessions now start with orange blocks in addition to the "(g)":
  "🟧🟧 (g) ". A title with the old bare "(g) " is upgraded on its next prompt.
- A retired guide's title is faded red instead of green: "🎟️🎟️ Sessions Manager (retired) 🎟️🎟️". Unicode has no pale red square, so 🎟️ is the
  closest match. The active guide stays 🟥🟥, and closed sessions stay ✅.

## [0.1.4] - 2026-10-29

### Added

- Open items have owners. The ledger's Open items section is a table, Item | Owner | Next action | Status. The
  owner is an existing session (title [id6]), "new session (proposed)", or the user; a row with no owner yet says
  ASK. Nothing is parked as "whenever you want" or FYI.
- After every worker report or handoff the guide re-reads it for loose ends ("not fixed", "out of scope", "FYI") and
  adds each one to the table. Workers list what they found but did not fix in their step reports.
- Every wake and every status reply puts the rows marked ASK, or proposing a new session not yet started, into the
  next ask: at most 4, each a recommended owner + action, with a worked example for money or business rules.
- A "Proposed actions" block in the status reply: actions on active sessions or new sessions to start, each
  answerable with yes or no.

### Changed

- Every "Streams" line in the status reply ends with "→ next: <action> (owner)".

## [0.1.3] - 2026-10-29

### Added

- Sweeps. Every wake runs `claude-top --once -n 30`; sessions active in the last 12 h with no ledger row are asked
  about in one batched "New sessions: … Manage, watch or ignore?" line, with a recommendation for each.
- Closing. `guide_title.py done <id>` (marker `done`) swaps a finished or obsolete worker's "(g) " for "✅ " (override:
  `SESSION_GUIDE_DONE_PREFIX`); `guided` and `mark` refuse it afterwards. The guide sends CLOSE, asks for a `result:`
  line, checks the state shows done, and lists `! claude stop <id>` for a session stuck on a dialog. Every STAND DOWN
  asks for the `result:` line too.
- A WATCHED session's unanswered question goes to the user; the answer is relayed in one message, the only one a
  WATCHED session gets.
- The guide prints its own context size in every status reply and hands off at 120k.

### Changed

- The guide title is "🟥🟥 Sessions Manager (2 managed · 1 watched · 3 new) 🟥🟥". new comes from a `New: <n>` line
  the guide writes into the ledger header on each sweep. `SESSION_GUIDE_TITLE` gains `{watched}` and `{new}`.

## [0.1.2] - 2026-10-28

### Added

- Guided prefix. Every MANAGED session's title starts with "(g) " so you can tell at a glance which sessions don't
  need you. `guide_title.py guided <id>` (run by `/session-guide join` and by the guide for sessions it starts or
  classifies MANAGED) adds it through the same hook; `unguided <id>` (on `/session-guide leave`, or a reclassify to
  WATCHED / IGNORED) takes it off. Never doubled, kept through renames and session-titles focus updates, never on a
  guide or a retired guide. Override: `SESSION_GUIDE_GUIDED_PREFIX`.

### Fixed

- `guide_title.py` refuses an empty session id (for example from a failed lookup) instead of acting on the current
  session. Id prefixes resolve from worktree project folders too.

## [0.1.1] - 2026-10-28

### Added

- Retired guides. When a guide takes over (or the user picks one of two guides), the old one is retired:
  `guide_title.py retire <id>` turns its title to "🟩🟩 Sessions Manager (retired) 🟩🟩" (override:
  `SESSION_GUIDE_RETIRED_TITLE`), and the hook never turns a retired id red again. The new guide asks it for a final
  message ending in a `result:` line so its state turns done, checks that, and marks it RETIRED in the ledger.
- An outgoing guide retires itself once its successor has introduced itself, instead of ending on a question.

## [0.1.0] - 2026-10-28

### Added

- The `session-guide` skill, packaged as a Claude Code plugin and marketplace, plus `install.sh` for a plain skill install.
- Guide mode:
  - advisory hard rules;
  - a sole-guide check;
  - MANAGED / WATCHED / IGNORED session levels;
  - batched relays;
  - numbered FINAL decisions with conflict checks;
  - the "Needs you now" status shape;
  - self-paced wakeups with back-off;
  - a ~120k guide handoff.
- Join and leave modes, so a worker can opt in with `/session-guide join` and out with `/session-guide leave`.
- `references/`: the worker contract, the ledger template and an example release playbook.
- `local.md` overrides and a `playbooks/` folder under `~/.claude/session-guide/`.
- `peek.py` (stdlib only, Python 3.9+): a session's title, context size, last reply, unanswered questions and last
  cross-session message.
- A pinned guide title, "🟥🟥 Sessions Manager (X of Y) 🟥🟥" with live MANAGED / WATCHED counts from the ledger:
  `guide_title.py mark|unmark|hook`, a `UserPromptSubmit` + `SessionStart` plugin hook that restores it after any
  rename, a `settings.json` snippet that `install.sh` prints for plain-skill installs, and a `SESSION_GUIDE_TITLE`
  override.
- A unittest suite on temp config dirs, CI on Ubuntu and macOS with Python 3.9 and 3.14, `scripts/demo.py`, issue
  templates, and a tag-driven release workflow.
