# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
- A unittest suite on temp config dirs, CI on Ubuntu and macOS with Python 3.9 and 3.14, `scripts/demo.py`, issue
  templates, and a tag-driven release workflow.
