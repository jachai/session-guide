#!/usr/bin/env python3
"""Tests for skills/session-guide/scripts/guide_title.py. Every test uses its own temp CLAUDE_CONFIG_DIR."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "session-guide", "scripts", "guide_title.py")
GUIDE = "c0ffee12-3456-4789-8abc-def012345678"
WORKER = "fa11ed00-1234-4567-89ab-cdef01234567"
TITLE = "🟥🟥 Sessions Manager (2 managed · 1 watched · 0 new) 🟥🟥"
LEDGER = """# release-2026-10-27 — guide ledger
Guide: 'release guide' [c0ffee12] since 10-27 09:00

## Streams
| Stream | Where now | Next step | Owner | Blocked on |
|---|---|---|---|---|
| Billing export | on staging | prod | 'billing export lead' [3fa9c1] | — |

## Sessions
| Title [id6] | Level | Role / stream | Worktree @ sha | Address | Ctx | Last seen |
|---|---|---|---|---|---|---|
| billing export lead [3fa9c1] | MANAGED | billing lead | worktrees/billing @a1b2c3d | uds | 140k | 12:35 |
| search reindex [a1a1a1] | MANAGED | reindex | worktrees/search @b2c3d4e | uds | 40k | 12:30 |
| design spike [b5c6d7] | WATCHED | — | — | — | 90k | 12:02 |
| old lead [c1c1c1] | HANDED OFF | billing | — | — | 210k | 10:00 |
| personal notes [e8f9a0] | IGNORED | off path | | | | |

## Decisions (FINAL unless struck)
1. (10-27 10:10, user in guide) A MANAGED | WATCHED table-looking line outside Sessions is not counted.
"""


class GuideTitleTest(unittest.TestCase):
    def setUp(self):
        self.cfg = tempfile.mkdtemp(prefix="guide-title-")
        self.ledger = os.path.join(self.cfg, "session-guide", "release-2026-10-27", "ledger.md")
        os.makedirs(os.path.dirname(self.ledger))
        with open(self.ledger, "w") as f:
            f.write(LEDGER)

    def tearDown(self):
        shutil.rmtree(self.cfg)

    def run_script(self, *args, stdin="", **extra_env):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_CODE_SESSION_ID", "SESSION_GUIDE_TITLE", "SESSION_GUIDE_GUIDED_PREFIX",
                            "SESSION_GUIDE_DONE_PREFIX", "SESSION_GUIDE_WATCHED_PREFIX")}
        env.update(CLAUDE_CONFIG_DIR=self.cfg, **extra_env)
        return subprocess.run([sys.executable, SCRIPT] + list(args), input=stdin, capture_output=True, text=True,
                              env=env)

    def hook(self, session_id=GUIDE, event="UserPromptSubmit", title=None, **extra_env):
        event_in = {"session_id": session_id, "hook_event_name": event}
        if title is not None:
            event_in["session_title"] = title
        return self.run_script("hook", stdin=json.dumps(event_in), **extra_env)

    def guide_title(self, **extra_env):
        r = self.hook(**extra_env)
        return json.loads(r.stdout)["hookSpecificOutput"]["sessionTitle"] if r.stdout else None

    def worker_title(self, title, event="UserPromptSubmit", **extra_env):
        """The title the hook sets on WORKER, or None when it prints nothing."""
        r = self.hook(WORKER, event, title, **extra_env)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        return json.loads(r.stdout)["hookSpecificOutput"]["sessionTitle"] if r.stdout else None

    def test_marked_session_gets_exact_title_with_counts(self):
        self.assertEqual(self.run_script("mark", self.ledger, "--session", GUIDE).returncode, 0)
        for event in ("UserPromptSubmit", "SessionStart"):
            r = self.hook(event=event)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout), {"hookSpecificOutput": {
                "hookEventName": event,
                "sessionTitle": TITLE}})

    def test_counts_follow_the_ledger(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        with open(self.ledger, "w") as f:
            f.write(LEDGER.replace("| design spike [b5c6d7] | WATCHED", "| design spike [b5c6d7] | MANAGED"))
        self.assertEqual(self.guide_title(), "🟥🟥 Sessions Manager (3 managed · 0 watched · 0 new) 🟥🟥")

    def test_title_format_can_be_overridden(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        stdin = json.dumps({"session_id": GUIDE, "hook_event_name": "UserPromptSubmit"})
        r = self.run_script("hook", stdin=stdin, SESSION_GUIDE_TITLE="guide {managed}/{active}")
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["sessionTitle"], "guide 2/3")
        r = self.run_script("hook", stdin=stdin, SESSION_GUIDE_TITLE="guide {oops}")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_unmarked_session_prints_nothing(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        r = self.hook(session_id="badc0de0-0000-4000-8000-000000000000")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_unmark_stops_the_title(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertEqual(self.run_script("unmark", "--session", GUIDE).returncode, 0)
        r = self.hook()
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_bad_ledger_prints_nothing(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        for content in ("no sessions table here\n", None):
            if content is None:
                os.remove(self.ledger)
            else:
                with open(self.ledger, "w") as f:
                    f.write(content)
            r = self.hook()
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_bad_input_prints_nothing(self):
        for stdin in ("", "not json", "{}"):
            r = self.run_script("hook", stdin=stdin)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_mark_refuses_a_ledger_without_sessions(self):
        other = os.path.join(self.cfg, "notes.md")
        with open(other, "w") as f:
            f.write("# notes\n")
        self.assertNotEqual(self.run_script("mark", other, "--session", GUIDE).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "session-guide", "guides", GUIDE)))

    def test_mark_resolves_an_id_prefix(self):
        proj = os.path.join(self.cfg, "projects", "-tmp-repo")
        os.makedirs(proj)
        open(os.path.join(proj, GUIDE + ".jsonl"), "w").close()
        self.assertEqual(self.run_script("mark", self.ledger, "--session", GUIDE[:8]).returncode, 0)
        self.assertEqual(self.guide_title(), TITLE)

    def test_retired_guide_gets_the_faded_red_title_and_never_red_again(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertEqual(self.run_script("retire", GUIDE).returncode, 0)
        for event in ("UserPromptSubmit", "SessionStart"):
            self.assertEqual(json.loads(self.hook(event=event).stdout), {"hookSpecificOutput": {
                "hookEventName": event, "sessionTitle": "🎟️🎟️ Sessions Manager (retired) 🎟️🎟️"}})
        self.assertNotEqual(self.run_script("mark", self.ledger, "--session", GUIDE).returncode, 0)
        self.assertIn("(retired)", self.hook().stdout)

    def test_retire_works_on_an_unmarked_session_and_can_be_overridden(self):
        self.assertEqual(self.run_script("retire", GUIDE).returncode, 0)
        stdin = json.dumps({"session_id": GUIDE, "hook_event_name": "UserPromptSubmit"})
        r = self.run_script("hook", stdin=stdin, SESSION_GUIDE_RETIRED_TITLE="old guide")
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["sessionTitle"], "old guide")

    def test_guided_worker_gets_the_prefix_on_its_own_title(self):
        self.assertEqual(self.run_script("guided", WORKER).returncode, 0)
        title = "housing stage 0 PR A gate · Running e2e2 rows"
        for event in ("UserPromptSubmit", "SessionStart"):
            self.assertEqual(self.worker_title(title, event), "🟧🟧 (g) " + title)
        self.assertIsNone(self.worker_title(""))  # no title yet: nothing to prefix

    def test_guided_prefix_is_idempotent(self):
        self.run_script("guided", WORKER)
        self.run_script("guided", WORKER)
        self.assertIsNone(self.worker_title("🟧🟧 (g) billing lead · Waiting on CI"))  # focus updates keep it: no output
        self.assertEqual(self.worker_title("🟧🟧 (g) 🟧🟧 (g) billing lead"), "🟧🟧 (g) billing lead")
        self.assertEqual(self.worker_title("(g)billing lead"), "🟧🟧 (g) billing lead")

    def test_a_title_with_the_old_bare_g_is_upgraded(self):
        self.run_script("guided", WORKER)
        self.assertEqual(self.worker_title("(g) billing lead · Waiting on CI"), "🟧🟧 (g) billing lead · Waiting on CI")
        self.assertEqual(self.worker_title("(g) (g) billing lead"), "🟧🟧 (g) billing lead")
        self.assertEqual(self.worker_title("🟧🟧 billing lead"), "🟧🟧 (g) billing lead")

    def test_guided_prefix_can_be_overridden(self):
        self.run_script("guided", WORKER)
        self.assertEqual(self.worker_title("billing lead", SESSION_GUIDE_GUIDED_PREFIX="[g] "), "[g] billing lead")
        self.assertIsNone(self.worker_title("[g] billing lead", SESSION_GUIDE_GUIDED_PREFIX="[g] "))

    def test_unguided_takes_the_prefix_off_then_drops_the_marker(self):
        self.run_script("guided", WORKER)
        self.assertEqual(self.run_script("unguided", WORKER).returncode, 0)
        self.assertEqual(self.worker_title("🟧🟧 (g) billing lead · Waiting on CI"), "billing lead · Waiting on CI")
        self.assertIsNone(self.worker_title("billing lead · Waiting on CI"))
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "session-guide", "guides", WORKER)))
        self.assertIsNone(self.worker_title("(g) renamed by hand"))  # unmanaged now: the hook leaves it alone

    def test_guides_and_retired_guides_never_get_the_prefix(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertNotEqual(self.run_script("guided", GUIDE).returncode, 0)
        self.assertEqual(json.loads(self.hook(title="anything").stdout)["hookSpecificOutput"]["sessionTitle"],
                         TITLE)
        self.run_script("retire", GUIDE)
        self.assertNotEqual(self.run_script("guided", GUIDE).returncode, 0)
        self.assertEqual(self.run_script("unguided", GUIDE).returncode, 0)  # left as it is
        self.assertIn("(retired)", self.hook(title="anything").stdout)
        self.assertNotIn("(g)", self.hook(title="anything").stdout)

    def test_watched_session_gets_the_gray_blocks_and_no_g(self):
        self.assertEqual(self.run_script("watched", WORKER).returncode, 0)
        title = "design spike · Reading the diff"
        for event in ("UserPromptSubmit", "SessionStart"):
            self.assertEqual(self.worker_title(title, event), "⬜⬜ " + title)
        self.assertIsNone(self.worker_title("⬜⬜ " + title))  # focus updates keep it: no output
        self.assertEqual(self.worker_title("⬜⬜ ⬜⬜ design spike"), "⬜⬜ design spike")
        self.assertIsNone(self.worker_title(""))  # no title yet: nothing to prefix
        self.assertEqual(self.worker_title("design spike", SESSION_GUIDE_WATCHED_PREFIX="[w] "), "[w] design spike")

    def test_guided_and_watched_swap_prefixes(self):
        self.run_script("guided", WORKER)
        self.run_script("watched", WORKER)
        self.assertEqual(self.worker_title("🟧🟧 (g) billing lead"), "⬜⬜ billing lead")
        self.assertEqual(self.worker_title("(g) billing lead"), "⬜⬜ billing lead")
        self.run_script("guided", WORKER)
        self.assertEqual(self.worker_title("⬜⬜ billing lead"), "🟧🟧 (g) billing lead")

    def test_unwatched_takes_the_prefix_off_then_drops_the_marker(self):
        self.run_script("watched", WORKER)
        self.assertEqual(self.run_script("unwatched", WORKER).returncode, 0)
        self.assertEqual(self.worker_title("⬜⬜ design spike"), "design spike")
        self.assertIsNone(self.worker_title("design spike"))
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "session-guide", "guides", WORKER)))
        self.assertIsNone(self.worker_title("⬜⬜ renamed by hand"))  # unmanaged now: the hook leaves it alone

    def test_watched_refuses_guides_retired_guides_and_closed_sessions(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertNotEqual(self.run_script("watched", GUIDE).returncode, 0)
        self.assertEqual(self.guide_title(), TITLE)
        self.run_script("retire", GUIDE)
        self.assertNotEqual(self.run_script("watched", GUIDE).returncode, 0)
        self.assertIn("(retired)", self.hook().stdout)
        self.run_script("done", WORKER)
        self.assertNotEqual(self.run_script("watched", WORKER).returncode, 0)
        self.assertEqual(self.worker_title("billing lead"), "✅ billing lead")

    def test_a_watched_session_that_becomes_the_guide_loses_the_prefix(self):
        self.run_script("watched", WORKER)
        self.assertEqual(self.run_script("mark", self.ledger, "--session", WORKER).returncode, 0)
        self.assertEqual(self.worker_title("⬜⬜ billing lead"), TITLE)

    def test_an_empty_or_unknown_id_is_an_error_not_this_session(self):
        for cmd in ("guided", "unguided", "retire"):
            for sid in ("", "  ", "deadbeef"):
                r = self.run_script(cmd, sid, CLAUDE_CODE_SESSION_ID=WORKER)
                self.assertNotEqual(r.returncode, 0, (cmd, sid))
        self.assertNotEqual(self.run_script("mark", self.ledger, "--session", "", CLAUDE_CODE_SESSION_ID=WORKER)
                            .returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "session-guide", "guides", WORKER)))
        self.assertEqual(self.run_script("guided", CLAUDE_CODE_SESSION_ID=WORKER).returncode, 0)  # no id: this one
        self.assertEqual(self.worker_title("billing lead"), "🟧🟧 (g) billing lead")

    def test_an_id_prefix_resolves_from_a_worktree_project_folder(self):
        for proj in ("-tmp-repo", "-tmp-repo--claude-worktrees-billing"):  # moved into a worktree mid-session
            os.makedirs(os.path.join(self.cfg, "projects", proj))
        open(os.path.join(self.cfg, "projects", "-tmp-repo--claude-worktrees-billing", WORKER + ".jsonl"), "w").close()
        self.assertEqual(self.run_script("guided", WORKER[:8]).returncode, 0)
        open(os.path.join(self.cfg, "projects", "-tmp-repo", WORKER + ".jsonl"), "w").close()  # in both: one session
        self.assertEqual(self.run_script("unguided", WORKER[:8]).returncode, 0)
        self.assertEqual(self.worker_title("(g) billing lead"), "billing lead")

    def test_a_guided_worker_that_becomes_the_guide_loses_the_prefix(self):
        self.run_script("guided", WORKER)
        self.assertEqual(self.run_script("mark", self.ledger, "--session", WORKER).returncode, 0)
        self.assertEqual(self.worker_title("(g) billing lead"), TITLE)

    def test_new_count_comes_from_the_ledger_header(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        with open(self.ledger, "w") as f:
            f.write(LEDGER.replace("since 10-27 09:00\n", "since 10-27 09:00\nNew: 3 (untracked, active <12h; 12:10)\n")
                    + "New: 9 (outside the header: not counted)\n")
        self.assertEqual(self.guide_title(), "🟥🟥 Sessions Manager (2 managed · 1 watched · 3 new) 🟥🟥")
        self.assertEqual(self.guide_title(SESSION_GUIDE_TITLE="{managed}/{watched}/{new} of {active}"), "2/1/3 of 3")

    def test_done_session_gets_the_check_prefix_in_place_of_g(self):
        self.run_script("guided", WORKER)
        self.assertEqual(self.run_script("done", WORKER).returncode, 0)
        for event in ("UserPromptSubmit", "SessionStart"):
            self.assertEqual(self.worker_title("(g) billing lead · PR merged", event), "✅ billing lead · PR merged")
        self.assertIsNone(self.worker_title("✅ billing lead · PR merged"))  # already right: no output
        self.assertEqual(self.worker_title("✅ (g) ✅ billing lead"), "✅ billing lead")
        self.assertEqual(self.worker_title("🟧🟧 (g) billing lead"), "✅ billing lead")
        self.assertEqual(self.worker_title("⬜⬜ billing lead"), "✅ billing lead")
        self.assertEqual(self.worker_title("billing lead", SESSION_GUIDE_DONE_PREFIX="[done] "), "[done] billing lead")
        self.assertEqual(self.run_script("done", WORKER).returncode, 0)  # a repeat is harmless
        with open(os.path.join(self.cfg, "session-guide", "guides", WORKER)) as f:
            self.assertEqual(f.read(), "done\n")

    def test_done_is_never_g_or_red_again(self):
        self.run_script("done", WORKER)
        self.assertNotEqual(self.run_script("guided", WORKER).returncode, 0)
        self.assertNotEqual(self.run_script("mark", self.ledger, "--session", WORKER).returncode, 0)
        self.assertEqual(self.run_script("unguided", WORKER).returncode, 0)  # left as it is
        self.assertEqual(self.worker_title("billing lead"), "✅ billing lead")

    def test_done_refuses_guides_and_empty_ids(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertNotEqual(self.run_script("done", GUIDE).returncode, 0)
        self.assertEqual(self.guide_title(), TITLE)
        self.run_script("retire", GUIDE)
        self.assertNotEqual(self.run_script("done", GUIDE).returncode, 0)
        self.assertIn("(retired)", self.hook().stdout)
        self.assertNotEqual(self.run_script("done", "", CLAUDE_CODE_SESSION_ID=WORKER).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "session-guide", "guides", WORKER)))


if __name__ == "__main__":
    unittest.main()
