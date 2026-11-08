# Two guides on two machines

Remote Control puts your other machines' sessions (and cloud sessions) in this machine's `ListAgents`. A guide on
each machine then sees the other guide and its workers. Without a scope, the old rules let one guide retire the
other, introduce itself to the other's workers, or ask you to classify sessions it can never peek. Give each machine's
guide its own scope name, and tell each one about the other.

The example below has two scopes: `hub` on one machine and `create` on the other. Use your own names, one short
word each.

## 1. Title and worker prefix (each machine's `~/.claude/settings.json`, under `"env"`)

Machine A (`hub`):

```json
"SESSION_GUIDE_TITLE": "🟥🟥 Sessions Manager · hub ({managed} managed · {watched} watched · {active} active · {new} new) 🟥🟥",
"SESSION_GUIDE_GUIDED_PREFIX": "🟧🟧 (g·hub) "
```

Machine B (`create`):

```json
"SESSION_GUIDE_TITLE": "🟥🟥 Sessions Manager · create ({managed} managed · {watched} watched · {active} active · {new} new) 🟥🟥",
"SESSION_GUIDE_GUIDED_PREFIX": "🟧🟧 (g·create) "
```

Keep the title starting with "🟥🟥 Sessions Manager": claude-top matches that start for a guide with no marker. The
default title already carries the ledger's slug (`{slug}`), so you can skip `SESSION_GUIDE_TITLE` if your ledgers'
slugs differ; `{host}` (this machine's short host name) is there too if you write your own.

## 2. Tell each guide about the other (`~/.claude/session-guide/local.md`)

On machine A, with machine B's guide ref from `ListAgents`:

```markdown
## Other guides
- [<B's ref>] create guide, machine B: never retire, introduce yourself to, classify or message it or any (g·create) row. Any ListAgents row labelled Remote Control belongs to another machine or the cloud unless its [ref] or title matches one of our Sessions rows (then it is an offline remote copy of our own session).
```

On machine B, with machine A's guide ref:

```markdown
## Other guides
- [<A's ref>] hub guide, machine A: never retire, introduce yourself to, classify or message it or any (g·hub) row. Any ListAgents row labelled Remote Control belongs to another machine or the cloud unless its [ref] or title matches one of our Sessions rows (then it is an offline remote copy of our own session).
```

Each guide also records the other on its ledger's `Other guides:` header line.

## 3. Restart

Hooks read `settings.json` when a session starts, so the new title and prefix show in sessions started afterwards.
The guide's own title changes on its next prompt after a restart; workers marked with the old "🟧🟧 (g) " get the new
prefix on their next prompt (the hook strips the default one before adding yours).
