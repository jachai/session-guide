# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
