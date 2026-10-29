# Ledger template

Path: `<config>/session-guide/<slug>/ledger.md`. Rewrite sections **in place** so they always describe *now*.
Only `## Log` is append-only, and it keeps the last ~15 lines. Trim older ones; the Decisions list keeps the durable
facts. Aim for under 6 KB: a fresh guide reads this file and nothing older. Write titles without the "(g) " prefix
that MANAGED workers carry, or the "✅ " of closed ones: the Level column already says so. `New:` is the count of
sessions active in the last 12 h with no Sessions row, from the guide's last sweep; the guide's title shows it.

```markdown
# <slug> — guide ledger
Guide: '<guide title>' [id8] since <date HH:MM>          (or: HANDING OFF to next guide)
Updated: <date HH:MM>   Usage: <plan usage, if you track it>
New: <n> (untracked sessions active <12h, sweep HH:MM)

## Streams
| Stream | Where now | Next step | Owner | Blocked on |
|---|---|---|---|---|
| Billing export | develop a1b2c3d on staging | fix rounding row → copy PR | 'billing export lead' [3fa9c1] | — |
| Search reindex | prod since 10-26 11:47Z, verified | read-only prod audit | worker TBD | traffic |
| Docs refresh | DONE | — | — | — |

## Order / gates
- Prod order: billing export → search reindex. One production merge at a time, each after the previous deploy.
- Gates in force: <playbook name>.

## Sessions
| Title [id6] | Level | Role / stream | Worktree @ sha | Address | Ctx | Last seen |
|---|---|---|---|---|---|---|
| billing export lead [3fa9c1] | MANAGED | billing lead | worktrees/billing @a1b2c3d | <from= address> | 140k | 12:35 |
| design spike [b5c6d7] | WATCHED | — | — | — | 90k | 12:02 |
| personal notes [e8f9a0] | IGNORED | off path | | | | |
| search reindex lead [d4e5f6] | DONE | closed 10-27 11:50, result line in | — | — | 160k | 11:50 |
| release guide [c0ffee] | RETIRED | previous guide, handed over 10-27 09:00 | — | — | 121k | 09:00 |

## Decisions (FINAL unless struck)
1. (10-26 10:10, user in guide) Test battery: only NEW failures block a prod merge; older ones go to the PR body and a ticket.
2. ~~(10-27 12:50, user to lead) Partial refunds: keep as built.~~ superseded by 3
3. (10-27 13:10, user in guide) Partial refunds follow who-pays.
   Example: order 600.00, customer returns 1 of 3 items (200.00), store at fault → customer refunded 200.00, fee waived.

## Waiting on the user
- Merge #142 — 'billing export lead' [3fa9c1] — asked 12:40, reminded no

## Open items (not blockers)
- Skill-edit proposal from the billing lead (awaiting yes)

## Log (last ~15)
- 10-27 11:51 battery re-run 64/66; rows 8 and 68 fail → relayed to the billing lead.
```
