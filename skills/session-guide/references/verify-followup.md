# Verify follow-up (worker brief)

The guide starts this read-only session when the user says yes to a follow-up (SKILL §7, Follow-ups). It checks that a
fix or deployment that reached production or staging does what it was meant to do, using the code, the intended
behaviour, the database and the logs. Fill in the `<...>` fields, then start it with `claude --bg --model sonnet --effort medium`
from the repository the change lives in (`model-choice.md`). The title is `verify <thing>`, for example `verify #142`.

Tools are named by role. If `<config>/session-guide/local.md` names your real ones (your read-only production database
tool, your log search tool, your staging database tool), put those names into the brief.

## Brief (send as-is, fields filled)

```
VERIFY (read-only): check that <thing: PR #N / version> does what it was meant to do on <prod | staging>.

What shipped: <one line: the fix or feature, in plain words>
Where and when: <deploy line from the ledger: environment, deploy time with timezone, deployed sha>
Intended behaviour: <the PR body's summary and the guide's Decisions that apply, verbatim with their numbers,
  e.g. "Decision 245 FINAL: ...">
Tools: <your read-only prod DB tool> for data, <your log search tool> for logs. <anything local.md says about access>

Rules
- READ-ONLY. No writes anywhere: no INSERT, UPDATE, DELETE or DDL, no migrations, no deploys, no reruns of jobs, no
  merges, no pushes, no PR or ticket edits, no messages to people outside this session's guide. SELECT only, preferably
  aggregates (counts, sums, min/max) and ids. No personal data (names, emails, addresses, phone numbers) in your report:
  use ids.
- Never AskUserQuestion. Questions go to the guide in plain words with your recommendation.
- Keep queries cheap: always filter by time (since the deploy) and limit rows.

Steps
1. Code. Read the merged diff (`gh pr view <N> --json mergeCommit,body,files` and `gh pr diff <N>`, or
   `git log`/`git show` for a version). Name the code paths that changed: functions, endpoints, jobs, migrations.
2. Expected behaviour. Write down, in concrete terms, what should now happen and what should no longer happen. Use
   numbers wherever money is involved: a worked example with amounts before and after (e.g. "order 600.00, 1 of 3
   items returned at 200.00 → refund 200.00, fee 0.00; before the fix the fee was 15.00"). Say which rows or log
   lines would prove it, and which would show it broken.
3. Data. With the read-only database tool, find the records the changed paths touched since the deploy time. Report
   counts, the ids of a few examples, and for each whether it matches step 2 (recompute any money from the stored
   inputs and compare). Look for the old wrong behaviour too: rows created since the deploy that still show it.
4. Logs. With the log search tool, search since the deploy for errors, exceptions, refusals and warnings on the changed
   paths, and for the log lines that show the new code ran. Compare the error rate with the same span before the
   deploy if it is cheap.
5. Verdict, one of:
   - verified: the changed paths ran on real data since the deploy and every case checked matches step 2;
   - not exercised yet: no traffic reached the changed paths since the deploy (say what would exercise them, and when
     it is likely);
   - broken: at least one case contradicts step 2, or the change raises new errors. Give the ids, the expected and
     actual values, and the log lines.

Report to the guide in ONE message:
  first line "VERIFIED: <thing>" / "NOT EXERCISED YET: <thing>" / "BROKEN: <thing>", then
  - expected behaviour (step 2, with the worked example);
  - evidence: queries run (text), counts, example ids, log searches and their hit counts, time span covered;
  - anything you found but did not check or fix (loose ends: other failures in the logs, data that looks wrong for
    another reason, a test that should exist), each as one line the guide can give an owner;
  - context size.
End your final message with a line `result: <thing> <verified | not exercised yet | broken>`.
```

## What the guide does with the report

- Records it: `guide_title.py verification "<thing> <short name>" <verified | not-exercised | broken> "<title [id6]>:
  <one-line evidence>"`. A not-exercised row comes back as a re-check after 24 hours (`--recheck-hours` to change).
- **Broken** becomes an Open items row for a fix, with the worker's evidence, and goes into the next interview first:
  something real may be wrong in production.
- Every loose end in the report becomes an Open items row (SKILL §4, Open items).
- Closes the session (SKILL §6) once the report is in and recorded.
