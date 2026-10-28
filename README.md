<p align="center"><img src="docs/icon-256.png" width="96" alt=""></p>

# session-guide

One Claude Code session that keeps your parallel sessions, and you, on the same page. When three features are moving
toward production in five background sessions at once, session-guide turns one more session into the **guide**. It
reads what every worker last said, routes each worker's questions to you as one interview, relays your rulings back,
wakes itself while CI and deploys run, and tells you exactly which session needs you, and for what.

[![test](https://github.com/jachai/session-guide/actions/workflows/test.yml/badge.svg)](https://github.com/jachai/session-guide/actions/workflows/test.yml)
[![release](https://img.shields.io/github/v/release/jachai/session-guide)](https://github.com/jachai/session-guide/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/jachai/session-guide/blob/main/LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)

A typical answer when you ask the guide "what's next?":

```
**Needs you now**
1. Merge #142 (green, mergeable, no deploy running) — https://github.com/you/app/pull/142
2. 'search reindex worker' [b5c6d7]: one refund rule to decide (below)

**Streams**
- Billing export: develop copy green → next: your merge, staging gate (owner: 'billing export lead' [3fa9c1])
- Search reindex: on staging → next: backfill after the refund rule
- Docs refresh: DONE (deploy job green 11:47Z)

**Running on its own**
- billing CI on main, next check ~14:20

Decision pending: refund the 5.00 restocking fee on a store-at-fault partial return?
```

## Why

Long multi-session efforts break down in predictable ways. Each of these happened in real use before session-guide
had a rule for it:

| What went wrong | What session-guide does |
|---|---|
| You answer a worker one way and the guide another. The worker builds the wrong one. | Workers never ask you directly. Every decision goes through the guide, is logged as **Decision N FINAL**, and is relayed verbatim. If you do answer a worker directly, the guide checks that answer against earlier decisions first. |
| Each fresh guide re-reads a growing pile of notes and gives advice from a stale picture. | One **ledger** per effort, rewritten in place and kept under ~6 KB. A new guide reads it and nothing older. |
| Status files lag. You get sent to answer a question you already answered. | Before every "what's next", `peek.py` reads the workers' own transcripts: last reply, unanswered questions, context size. |
| Two guides are running and give you conflicting advice. | Sole-guide check at start: the guide asks you which one stays and tells the other to stand down. |
| "be0f7c41 is waiting on you." Which one is that? | Sessions are always named by title, with the id in brackets. |
| The guide sits idle while a deploy finishes, or wakes every 10 minutes all night. | +5 min wakeups for imminent events and +10 for long runs. When only you can unblock things, it backs off to +30 and +60, then stops. |
| A guide runs out of context mid-relay. | It hands off at ~120k: ledger current, wakeups cancelled, a one-line prompt for the next guide. |

## Install

As a Claude Code plugin:

```
/plugin marketplace add jachai/session-guide
/plugin install session-guide@session-guide
```

Or as a plain skill, without the plugin system:

```sh
git clone https://github.com/jachai/session-guide
cd session-guide && ./install.sh          # copies the skill to ~/.claude/skills (--link to symlink instead)
```

You need Claude Code with background sessions and cross-session messaging (`SendMessage`, `ListAgents`), and Python
3.9+ for the transcript reader. There are no dependencies. [claude-top](https://github.com/jachai/claude-top) is
optional but makes the session list nicer.

## Use

In the session you want as the guide:

```
/session-guide
```

(`/session-guide:session-guide` when installed as a plugin.) Tell it what the streams are: "guide me through
releasing billing export, search reindex and the docs refresh". It creates the ledger, finds the live sessions,
classifies them, and answers in the shape above.

In each worker you want managed:

```
/session-guide join
```

The worker finds the live guide, adopts the [worker contract](skills/session-guide/references/worker-contract.md)
and registers. From then on it reports at step boundaries and sends its questions to the guide. `/session-guide
leave` opts it back out. Sessions the guide starts itself are managed automatically.

| Level | How a session gets it | What the guide does |
|---|---|---|
| **MANAGED** | `/session-guide join`, or started by the guide | Sends the contract, relays rulings and approvals, takes its questions |
| **WATCHED** | Any other session the guide sees (the default) | Reads it for status and never messages it. Asks you once: manage, watch or ignore? |
| **IGNORED** | You said so | Leaves it alone |

Other commands: `/session-guide handoff` makes the guide hand off now. Say "take over as guide, ledger: <path>" in a
fresh session to continue.

## What the guide will and won't do

The guide is **advisory**. It never branches, commits, pushes, merges or edits code: merges stay with you, and
building stays with the workers. It may:

- read transcripts, `ListAgents`, and CI/PR/deploy state;
- message managed workers and relay your approvals;
- start fresh worker sessions (`claude --bg`) from a worker's resume prompt;
- write the ledger.

Browser checks, test batteries on shared environments, and database and log checks go to a worker or to you.

## The ledger

`~/.claude/session-guide/<slug>/ledger.md` holds Streams, Order/gates, Sessions, Decisions (numbered, FINAL unless
struck), Waiting on you, Open items, and a 15-line log. See the
[template](skills/session-guide/references/ledger-template.md). It's plain Markdown, so you can read and edit it
yourself.

## Make it yours

- **`~/.claude/session-guide/local.md`**: rules that override the skill where they conflict, such as your name, your
  cost-guard phrase, or "never defer work for usage limits without asking". It's read first in every mode.
- **`~/.claude/session-guide/playbooks/*.md`**: your release gates, commands and URLs. The guide loads the one that
  fits when a stream heads to staging or production, falling back to the
  [example playbook](skills/session-guide/references/release-playbook.md).

## peek.py

The transcript reader the guide uses. You can use it directly:

```
$ python3 skills/session-guide/scripts/peek.py b5c6d7e8
=== search reindex worker · Waiting on a refund rule [b5c6d7e8] · last write 10-27 14:05 · ctx 88k
ASKED (WAITING ON AN ANSWER):
  - Partial refund on a 3-item order (600.00), customer returns 1 item (200.00), store at fault: refund the 5.00 restocking fee too?
LAST TEXT: The reindex is done on staging, but one rule needs a decision before I write the backfill. Details below.
```

It is read-only, stdlib only, and honors `CLAUDE_CONFIG_DIR`. `python3 scripts/demo.py` runs it on made-up sessions.

More detail: [how it works](docs/how-it-works.md).

## Notes

- Everything stays on your machine. The skill adds no network calls; the only messages are between your own local
  sessions.
- If you run a cost guard that caps messages to the same agent, exempt messages to other top-level sessions. A guide
  relays many times per session by design.
- Contributions welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).
