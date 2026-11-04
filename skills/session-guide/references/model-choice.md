# Model and effort per session

This table and its `claude --bg` commands are the Claude Code adapter. In Codex, follow
[`codex-runtime.md`](codex-runtime.md): inherit the current model by default, use only model/effort values exposed by
the current collaboration tool, and never present Claude `/model` or `/effort` commands as Codex controls.

The guide picks a model and an effort for every session it starts, and checks them on every session it takes over or
starts to manage (SKILL §2, §6, §7). Pick for the task the session does **next**, not for the stream as a whole.

Use aliases, never dated ids: `opus`, `sonnet`, `haiku`. An alias always means the newest model of that line, so this
table stays current. If `<config>/session-guide/local.md` names a different top model (for example `fable`), use it
wherever this table says `opus`. Efforts are `low`, `medium`, `high`, `xhigh` and `max`.

## The table

Match the model to what a subtle mistake would cost, not to how big the task is. When a task fits two rows, take the
higher one.

| Task the session does next | Model | Effort | Why, in cost terms |
|---|---|---|---|
| Money or business-rule fix, data migration or backfill, anything where a mistake ships silently | opus | high | One wrong refund or migrated row costs more than the whole session. |
| Release gate, design review, final review before a merge, a verdict the guide will act on | opus | high | A cheap wrong "green" is the most expensive outcome the guide can get. |
| Well-specified build or fix with a clear acceptance test (named findings, a failing test, a UI change) | opus | medium | Needs code judgment, but the test catches most slips; medium saves thinking on every turn. |
| Next guide (§8 handoff) | opus | medium | Interviews and money examples need judgment; most turns only read and relay. |
| Verify follow-up (`verify-followup.md`, read-only) | sonnet | medium | Reads code, runs SELECTs and searches logs against a stated expectation; several times cheaper than opus. |
| Mechanical edit: rename, copy or docs change, version bump, changelog, a test rewrite with a grep check | sonnet | low | The check is mechanical, so a bigger model buys nothing. |
| CI read, read-only data check, status report, log search, sweep | sonnet | low | Read and summarize; the guide judges the result. |
| One lookup or one command with nothing to judge | haiku | low | The cheapest model; anything with a judgment call goes up a row. |

A task that grows changes its row: a "mechanical" session that starts touching money logic moves up to opus/high.

## Starting a session (SKILL §6)

```
claude --bg --model <alias> --effort <level> --name '<title>' "<prompt>"
```

Write the pick in the ledger's Sessions row, Model / effort column: `sonnet/low`.

A successor of a worker that handed off gets a fresh pick for the **next step's** task, never a copy of its
predecessor's: an opus/high session that finished a refund fix hands off to a sonnet/low session that only reads CI.

## Checking a session the guide didn't start (SKILL §2, §7)

1. Read what it runs: claude-top's MODEL and EFFORT columns (`claude-top --once`), or the end of `peek.py <id8>`'s
   first line ("· claude-opus-5-5 / high"). Write it in the Sessions row.
2. Compare with the table for the task it is doing now. Suggest a switch only when the model differs, or the effort is
   two or more steps away (low against high). One step is noise.
3. Put the suggestion in the interview as something only the user can do, since the guide can't switch another
   session:

   > 'billing CI watcher' [3fa9c1] runs opus/high on CI reads and status reports; switch to sonnet/low? Open it from
   > `claude agents` and type `/model sonnet`, then `/effort low`, in its window; this may also become your default
   > for new sessions. (switch recommended)

   Options: Switched / Keep as is. On Switched, check it on the session's next turn (claude-top or peek) and update the
   row. On Keep as is, write "kept" in the row ("opus/high, kept 11-03"), and don't ask again until its task changes.
4. Don't suggest a switch to a session near its context limit (over ~150k) or about to finish: the first turn after a
   model switch re-reads the whole context at the new model's uncached price. Re-pick for its successor instead.

`/model <alias>` and `/effort <level>` both work mid-session. Claude Code may also save either one as the user's
default for new sessions (`/effort max` is this session only), so the question says so: "this may also become your
default for new sessions". Sessions the guide starts pass `--model` and `--effort`, so that default doesn't reach them.
