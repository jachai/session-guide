# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
