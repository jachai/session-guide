# Release playbook (example)

A generic develop → staging → production playbook. Copy it to `<config>/session-guide/playbooks/<name>.md` and
replace the commands, URLs and gates with your own. The guide prefers your playbook over this file. The guide checks
gates through CI state and worker evidence. Workers or the user run the browser, database and log checks.

## Branch shape
- Cut release branches from the production branch. Before the production PR, merge the production branch into the
  release branch, never the integration branch.
- Several ready PRs to the same base can be bundled so the base deploys once.

## Staging gate (before any production PR merges)
1. The integration PR's CI is green.
2. The user merges it. The integration pipeline then runs tests, migrations and the staging deploy, and every job
   must be green (`gh run list --branch <integration> -L 3`, then `gh run view <id>`).
3. A worker runs the feature checks on staging (browser + database) and puts the evidence in the production PR body.
4. The full regression battery runs on staging. Only NEW failures block; known ones go in the PR body and a ticket.
   Classify every failure as stale test or real behavior change **before** anyone fixes it. One battery at a time,
   and no staging deploy mid-battery.
5. After the production deploy, a worker runs read-only production checks and the guide records them in the ledger.

## Production merges
- Follow the ledger's order. **One production merge at a time:** merge the next only after the previous pipeline's
  deploy job has finished. Two merges seconds apart can deploy the older build last.
- Before saying "merge now", check that the PR's checks are green, it is mergeable, no other production pipeline is
  mid-deploy, and whether either side adds migrations.
- To verify a deploy, confirm the pipeline is green and the deploy job succeeded, and name the deployed sha.

## Typical durations (for choosing wakeups)
full CI ~12 min · staging deploy ~10 min after tests · regression battery 15–70 min · production deploy ~15 min.
