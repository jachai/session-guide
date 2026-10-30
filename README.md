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
- Billing export: develop copy green → next: your merge, then the staging gate ('billing export lead' [3fa9c1])
- Search reindex: on staging → next: backfill after the refund rule ('search reindex worker' [b5c6d7])
- Docs refresh: DONE (deploy job green 11:47Z)

**Proposed actions**
1. Start a new session 'billing rounding fix' for the 0.01 rounding on split invoices the billing lead left
   out of scope: yes/no?
2. 'search reindex worker' [b5c6d7] runs the read-only prod audit after the backfill: yes/no?

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
| Two guides are running and give you conflicting advice. | Sole-guide check at start: the guide asks you which one stays and retires the other (faded red title, state done). |
| "be0f7c41 is waiting on you." Which one is that? | Sessions are always named by title, with the id in brackets. |
| The guide sits idle while a deploy finishes, or wakes every 10 minutes all night. | +5 min wakeups for imminent events and +10 for long runs. When only you can unblock things, it backs off to +30 and +60, then stops. |
| A guide runs out of context mid-relay. | It prints its own context size in every status reply and hands off at 120k: ledger current, wakeups cancelled, a one-line prompt for the next guide. |
| A worker's report says "not fixed, out of scope". Nobody picks it up, and the guide lists it as "open, whenever you want". | After every report the guide adds each loose end to an Open items table with an owner: a session, a new session it proposes, or you. Owner-less items go into the next interview, at most 4 at a time, each as a recommended owner + action you answer yes or no. |
| New sessions pile up unclassified, and finished ones sit "waiting" forever. | Every wake sweeps sessions active in the last 12 h and asks you once, in one line, whether to manage, watch or ignore each new one. Finished or obsolete workers are closed: ✅ title, `result:` line, state done, or a `! claude stop` for you when they are stuck. |

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
| **MANAGED** | `/session-guide join`, or started by the guide | Sends the contract, relays rulings and approvals, takes its questions. Its title starts with "🟧🟧 (g) " |
| **WATCHED** | Any other session the guide sees (the default) | Reads it for status. Asks you once: manage, watch or ignore? Its only message from the guide is your answer to a question it asked. Its title starts with "⬜⬜ " |
| **IGNORED** | You said so | Leaves it alone |
| **RETIRED** | A guide that handed over to a new one | Nothing: faded red title, state done |
| **DONE** | A MANAGED session the guide closed (finished or obsolete) | Nothing: "✅ " title, state done |

Other commands: `/session-guide handoff` makes the guide hand off now. Say "take over as guide, ledger: <path>" in a
fresh session to continue.

## Titles

One color per kind of session, so the agents view reads at a glance:

| Title | Session |
|---|---|
| `🟥🟥 Sessions Manager (2 managed · 1 watched · 3 new) 🟥🟥` | The active guide |
| `🎟️🎟️ Sessions Manager (retired) 🎟️🎟️` | A retired guide |
| `⬜⬜ design spike · Reading the diff` | WATCHED: the guide reads it but doesn't manage it |
| `🟧🟧 (g) billing export lead · Waiting on CI` | MANAGED: guided, you don't need to go in |
| `✅ search reindex lead · PR merged` | Closed by the guide |

Unicode has no pale red square, so the retired guide's 🎟️ is the closest match, a dusty pink-red block. Its look
varies by platform; override it with `SESSION_GUIDE_RETIRED_TITLE`.

### The guide's pinned title

The guide keeps one title, so you can always find it in the agents view:

```
🟥🟥 Sessions Manager (2 managed · 1 watched · 3 new) 🟥🟥
```

managed and watched count the ledger's MANAGED and WATCHED rows. new is the guide's count of sessions active in the
last 12 h that have no ledger row yet, which it writes into the ledger header (`New: 3`) on every sweep. At start the
guide runs
`scripts/guide_title.py mark <ledger>`. A `UserPromptSubmit` and `SessionStart` hook then re-applies the title on
every prompt, with fresh counts, so a rename (by hand or by another titling hook) lasts one turn at most. Every other
session is left alone: the hook prints nothing for it, and it prints nothing on any error too.

When a new guide takes over, the old one is retired with `guide_title.py retire <id>`. Its title turns to
`🎟️🎟️ Sessions Manager (retired) 🎟️🎟️` and never goes red again, and it ends with a `result:` line so its state shows
done rather than waiting on you.

A finished or obsolete worker is **closed** the same way: `guide_title.py done <id>` swaps its `🟧🟧 (g) ` for `✅ `, the
guide asks it for a final `result:` line, and checks its state turned done. If the session is stuck on a question or
a guard prompt, the guide hands you `! claude stop <id>` instead.

### Guided and watched sessions

Every MANAGED session's title starts with `🟧🟧 (g) `, for example `🟧🟧 (g) billing export lead · Waiting on CI`. Those are
the sessions you don't need to go into; a session without it may need you. `/session-guide join` and the guide run
`guide_title.py guided <id>`, and the same hook puts the prefix in front of the session's own title. It never doubles
up, it survives renames and focus updates, and it stays through DONE until the guide closes the session.
`guide_title.py unguided <id>` (on `/session-guide leave`, or when the guide reclassifies a session IGNORED) takes
it off. The guide and a retired guide never get it. Override the prefix with `SESSION_GUIDE_GUIDED_PREFIX`.

Every WATCHED session's title starts with `⬜⬜ `, from `guide_title.py watched <id>`, with the same behavior:
`guided` and `watched` swap one prefix for the other when a session changes level. Override it with
`SESSION_GUIDE_WATCHED_PREFIX`.

- The plugin install registers the hook for you. A plain-skill install prints the `settings.json` snippet to add
  ([examples/settings-snippet.json](examples/settings-snippet.json)).
- If you use [session-titles](https://github.com/jachai/session-titles), the guide also runs
  `session-titles off <its id>` so the two hooks don't take turns. Guided and watched sessions keep session-titles on: its hook's title
  overrides this one, so `guide_title.py` also puts the prefix into its stored origin, and both give the same title.
- To use your own format, set `SESSION_GUIDE_TITLE`, for example `"guide {managed}/{watched}/{new}"`, in the `env`
  block of `settings.json` (`{active}` is managed + watched). Avoid `*`, because some title tools strip markdown, and
  keep it short, because the agents view and claude-top cut long names. claude-top spots a guide by its marker file
  and falls back to the `🟥🟥 Sessions Manager` start. The closed prefix is `SESSION_GUIDE_DONE_PREFIX`.

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
struck), Waiting on you, Open items (a table: Item | Owner | Next action | Status, where every row has an owner or
ASK), and a 15-line log. See the
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
