# Ledger template

Path: `<config>/session-guide/<slug>/ledger.md`. Rewrite sections **in place** so they always describe *now*.
Only `## Log` is append-only, and it keeps the last ~15 lines. Trim older ones; the Decisions list keeps the durable
facts. Aim for under 6 KB: a fresh guide reads this file and nothing older. Write titles without the "🟧🟧 (g) " or "⬜⬜ " prefix
that MANAGED and WATCHED sessions carry, or the "✅ " of closed ones: the Level column already says so. A session with no row is
new: the title hook counts those live, and the guide asks about them until each has a row.

**Sessions** has a Model / effort column: the guide's pick for a session it started (`sonnet/low`), or what a session it
took over runs, read from claude-top or peek. "kept <date>" records that the user turned down a switch, so the guide
doesn't ask again until the session's task changes (`references/model-choice.md`).

**Open items** is a table, not a list. Every row has an Owner: an existing session (title [id6]), "new session
(proposed)", or the user. A row with no owner yet says ASK in the Owner column. Next action is one concrete step
for that owner. Status is ASK <time> (in the user's next ask), waiting (with the next check), or DONE (how verified;
delete DONE rows after a day). Nothing sits here as "whenever you want".

**Waiting on the user** holds a table with one row per session that only the user can move, written by `guide_title.py
waiting` and `sleep`: the exact action with its full link or command, when it was first asked, and when to remind.
Remind at is `YYYY-MM-DD HH:MM`, local time; a value that can't be read counts as due. Bullets for items no session owns can
sit below the table. A MANAGED or WATCHED session with no row here that has gone quiet has to settle (SKILL §7).

**Verifications** is a table with one row per fix or deployment the guide proposed to check, written by `guide_title.py
verification`: Thing (its PR `#N` or version first; that is the key), Where (prod, staging, merged, released), Result
(proposed, running, verified, not-exercised, broken, skipped), when it was recorded, one line of evidence or the
verifying session, and for not-exercised when to re-check. `followups` lists recent deployments with no row here. The
`Last review:` line under the table is the time of the last follow-up review (`followups --reviewed`). Write deploy
lines in the Log with a date and the PR or version ("10-27 11:47 #142 ON PROD @a1b2c3d"), so `followups` finds them.

```markdown
# <slug> — guide ledger
Guide: '<guide title>' [id8] since <date HH:MM>          (or: HANDING OFF to next guide)
Updated: <date HH:MM>   Usage: <plan usage, if you track it>

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
| Title [id6] | Level | Role / stream | Model / effort | Worktree @ sha | Address | Ctx | Last seen |
|---|---|---|---|---|---|---|---|
| billing export lead [3fa9c1] | MANAGED | billing lead | opus/high | worktrees/billing @a1b2c3d | <from= address> | 140k | 12:35 |
| billing CI reader [2b3c4d] | MANAGED | billing CI reads | sonnet/low | worktrees/billing @a1b2c3d | <from= address> | 40k | 12:30 |
| design spike [b5c6d7] | WATCHED | — | opus/xhigh, kept 10-27 | — | — | 90k | 12:02 |
| notes cleanup [f1a2b3] | ACTIVE | — | — | — | — | — | 12:20 |
| personal notes [e8f9a0] | IGNORED | off path | | | | | |
| search reindex lead [d4e5f6] | DONE | closed 10-27 11:50, result line in | opus/medium | — | — | 160k | 11:50 |
| release guide [c0ffee] | RETIRED | previous guide, handed over 10-27 09:00 | — | — | — | 121k | 09:00 |

## Decisions (FINAL unless struck)
1. (10-26 10:10, user in guide) Test battery: only NEW failures block a prod merge; older ones go to the PR body and a ticket.
2. ~~(10-27 12:50, user to lead) Partial refunds: keep as built.~~ superseded by 3
3. (10-27 13:10, user in guide) Partial refunds follow who-pays.
   Example: order 600.00, customer returns 1 of 3 items (200.00), store at fault → customer refunded 200.00, fee waived.

## Waiting on the user
| Session [id6] | What the user needs to do | Asked | Remind at |
|---|---|---|---|
| billing export lead [3fa9c1] | Merge #142: https://github.com/acme/billing/pull/142 | 2026-10-27 12:40 | 2026-10-27 20:40 |

## Open items
| Item | Owner | Next action | Status |
|---|---|---|---|
| Rounding off by 0.01 on split invoices (billing lead report: "not fixed, out of scope") | new session (proposed) | start 'billing rounding fix' from develop | ASK 13:05 |
| Skill-edit proposal from the billing lead | the user | say yes or no to the edit | ASK 12:50 |
| Search reindex read-only prod audit | 'search reindex lead' [d4e5f6] | run the audit after traffic dips | waiting, next check ~15:00 |
| Stale feature flag in config | ASK | — | ASK 13:05 |

## Verifications
| Thing | Where | Result | Checked | Evidence / session | Re-check |
|---|---|---|---|---|---|
| #142 refund fee fix | prod | verified | 2026-10-27 15:10 | 'verify #142' [9a8b7c]: 41 refunds since deploy, all fees match, 0 errors | — |
| #139 export retry | staging | not-exercised | 2026-10-27 15:30 | 'verify #139' [8b7c6d]: no export ran since deploy | 2026-10-28 15:30 |
| v2.4.0 | prod | running | 2026-10-27 15:40 | 'verify v2.4.0' [7c6d5e] | — |

Last review: 2026-10-27 14:55

## Log (last ~15)
- 10-27 11:51 battery re-run 64/66; rows 8 and 68 fail → relayed to the billing lead.
```
