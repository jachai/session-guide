#!/usr/bin/env python3
"""Tests for skills/session-guide/scripts/guide_title.py. Every test uses its own temp CLAUDE_CONFIG_DIR."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "session-guide", "scripts", "guide_title.py")
GUIDE = "c0ffee12-3456-4789-8abc-def012345678"
WORKER = "fa11ed00-1234-4567-89ab-cdef01234567"
TITLE = "🟥🟥 Sessions Manager (2 managed · 1 watched · 0 active · 0 new) 🟥🟥"
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
                            "SESSION_GUIDE_DONE_PREFIX", "SESSION_GUIDE_WATCHED_PREFIX", "SESSION_GUIDE_ACTIVE_PREFIX")}
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
        self.assertEqual(self.guide_title(), "🟥🟥 Sessions Manager (3 managed · 0 watched · 0 active · 0 new) 🟥🟥")

    def test_title_format_can_be_overridden(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        stdin = json.dumps({"session_id": GUIDE, "hook_event_name": "UserPromptSubmit"})
        r = self.run_script("hook", stdin=stdin, SESSION_GUIDE_TITLE="guide {managed}/{tracked}")
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

    def titles_state(self, session_id=WORKER, **state):
        """Write a session-titles state file, the way that plugin does; returns a function that reads it back."""
        path = os.path.join(self.cfg, "session-titles", session_id + ".json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f)
        return lambda: json.load(open(path))

    def test_guided_goes_into_the_session_titles_origin(self):
        read = self.titles_state(origin="billing lead", focus="Waiting on CI", last_set="billing lead · Waiting on CI",
                                 history=["billing lead · Waiting on CI"])
        self.run_script("guided", WORKER)
        state = read()
        self.assertEqual(state["origin"], "🟧🟧 (g) billing lead")
        self.assertEqual(state["focus"], "Waiting on CI")
        self.assertEqual(state["last_set"], "🟧🟧 (g) billing lead · Waiting on CI")
        self.assertIn("billing lead · Waiting on CI", state["history"])  # its title now still reads as its own

    def test_session_titles_origin_follows_every_level_change(self):
        read = self.titles_state(origin="(g) billing lead", last_set="(g) billing lead")
        self.run_script("guided", WORKER)
        self.assertEqual(read()["origin"], "🟧🟧 (g) billing lead")  # an origin adopted from the old prefix upgrades
        self.run_script("watched", WORKER)
        self.assertEqual(read()["origin"], "⬜⬜ billing lead")
        self.run_script("unwatched", WORKER)
        self.assertEqual(read()["origin"], "billing lead")
        self.run_script("guided", WORKER)
        self.run_script("done", WORKER)
        self.assertEqual(read()["origin"], "✅ billing lead")

    def test_the_hook_syncs_a_session_marked_before_this_version(self):
        self.run_script("guided", WORKER)
        read = self.titles_state(origin="billing lead", last_set="billing lead")
        self.assertEqual(self.worker_title("billing lead"), "🟧🟧 (g) billing lead")
        self.assertEqual(read()["origin"], "🟧🟧 (g) billing lead")

    def test_guides_and_retired_guides_turn_session_titles_off(self):
        read = self.titles_state(GUIDE, origin="old name")
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertTrue(read()["off"])
        self.assertEqual(read()["origin"], "old name")
        read = self.titles_state(GUIDE, origin="old name")
        self.run_script("retire", GUIDE)
        self.assertTrue(read()["off"])

    def test_no_or_broken_session_titles_state_changes_nothing(self):
        self.assertEqual(self.run_script("guided", WORKER).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "session-titles")))
        path = os.path.join(self.cfg, "session-titles", WORKER + ".json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write("{broken")
        self.assertEqual(self.run_script("guided", WORKER).returncode, 0)
        self.assertEqual(self.worker_title("billing lead"), "🟧🟧 (g) billing lead")
        with open(path) as f:
            self.assertEqual(f.read(), "{broken")

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

    def transcript(self, session_id, title="", entrypoint="cli", age=0):
        path = os.path.join(self.cfg, "projects", "-tmp-repo", session_id + ".jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(json.dumps({"type": "user", "entrypoint": entrypoint}) + "\n")
            f.write(json.dumps({"type": "custom-title", "customTitle": title}) + "\n")
        os.utime(path, (time.time() - age, time.time() - age))

    def test_new_count_and_context_come_from_a_live_sweep(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertNotIn("additionalContext", self.hook().stdout)
        self.transcript(GUIDE, "the guide itself")
        self.transcript("3fa9c1d2-0000-4000-8000-000000000000", "has a row")
        self.transcript("b5c6d7e8-0000-4000-8000-000000000000", "watched row")
        self.transcript("11111111-0000-4000-8000-000000000000", "too old", age=13 * 3600)
        self.transcript("22222222-0000-4000-8000-000000000000", "a monitor tick", entrypoint="sdk-cli")
        self.transcript("33333333-0000-4000-8000-000000000000", "closed one")
        self.run_script("done", "33333333-0000-4000-8000-000000000000")
        self.transcript("44444444-0000-4000-8000-000000000000", "new one")
        self.assertEqual(self.guide_title(), "🟥🟥 Sessions Manager (2 managed · 1 watched · 0 active · 1 new) 🟥🟥")
        output = json.loads(self.hook().stdout)["hookSpecificOutput"]
        self.assertIn("'new one' [44444444]", output["additionalContext"])
        self.assertIn("AskUserQuestion", output["additionalContext"])
        for hidden in ("has a row", "watched row", "too old", "a monitor tick", "closed one", "the guide itself"):
            self.assertNotIn(hidden, output["additionalContext"])
        r = self.run_script("sweep", self.ledger, "--hours", "24", CLAUDE_CODE_SESSION_ID=GUIDE)
        self.assertIn("'too old' [11111111]", r.stdout)
        self.assertIn("New: 2", r.stdout)

    def test_a_new_session_stays_new_until_it_has_a_row(self):
        new = "44444444-0000-4000-8000-000000000000"
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.transcript(new, "new one")
        self.assertEqual(self.run_script("active", new).returncode, 0)  # blue already, still unanswered
        self.assertIn("[44444444]", self.hook().stdout)
        with open(self.ledger, "a") as f:
            f.write("\n## Sessions\n| new one [444444] | ACTIVE | | | | | |\n")
        self.assertNotIn("additionalContext", self.hook().stdout)
        self.assertIn("1 active · 0 new", self.guide_title())

    def test_workers_and_retired_guides_get_no_sweep(self):
        self.transcript("44444444-0000-4000-8000-000000000000", "new one")
        self.run_script("guided", WORKER)
        self.assertNotIn("additionalContext", self.hook(WORKER, title="billing lead").stdout)
        self.run_script("retire", GUIDE)
        self.assertNotIn("additionalContext", self.hook().stdout)

    def test_active_session_gets_the_blue_blocks(self):
        self.assertEqual(self.run_script("active", WORKER).returncode, 0)
        self.assertEqual(self.worker_title("notes cleanup"), "🟦🟦 notes cleanup")
        self.assertIsNone(self.worker_title("🟦🟦 notes cleanup"))
        self.run_script("watched", WORKER)
        self.assertEqual(self.worker_title("🟦🟦 notes cleanup"), "⬜⬜ notes cleanup")
        self.run_script("active", WORKER)
        self.assertEqual(self.worker_title("🟧🟧 (g) notes cleanup"), "🟦🟦 notes cleanup")
        self.assertEqual(self.worker_title("notes", SESSION_GUIDE_ACTIVE_PREFIX="[a] "), "[a] notes")
        self.run_script("unguided", WORKER)
        self.assertEqual(self.worker_title("🟦🟦 notes cleanup"), "notes cleanup")

    def test_active_refuses_guides_retired_guides_and_closed_sessions(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertNotEqual(self.run_script("active", GUIDE).returncode, 0)
        self.run_script("retire", GUIDE)
        self.assertNotEqual(self.run_script("active", GUIDE).returncode, 0)
        self.run_script("done", WORKER)
        self.assertNotEqual(self.run_script("active", WORKER).returncode, 0)

    def test_title_placeholders(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.assertEqual(self.guide_title(SESSION_GUIDE_TITLE="{managed}/{watched}/{active}/{new} of {tracked}"),
                         "2/1/0/0 of 3")

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

    def test_closed_sessions_and_repeated_rows_do_not_count(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        with open(self.ledger, "w") as f:  # topmost row wins; a closed session's rows are skipped; no id counts
            f.write(LEDGER.replace("| old lead [c1c1c1] |", "| search reindex again [a1a1a1deadbeef] | DONE | x | | | | |\n"
                                   "| search reindex old [a1a1a1] | MANAGED | x | | | | |\n| old lead [c1c1c1] |")
                    .replace("| personal notes [e8f9a0] | IGNORED", "| no id here | MANAGED | x | | | | |\n| personal notes [e8f9a0] | IGNORED"))
        # billing, search reindex (its topmost row; the two rows below it are skipped) and the row with no id
        self.assertEqual(self.guide_title(), "🟥🟥 Sessions Manager (3 managed · 1 watched · 0 active · 0 new) 🟥🟥")
        os.makedirs(os.path.join(self.cfg, "session-guide", "guides"), exist_ok=True)
        self.run_script("done", "3fa9c100-0000-4000-8000-000000000000")
        self.assertEqual(self.guide_title(), "🟥🟥 Sessions Manager (2 managed · 1 watched · 0 active · 0 new) 🟥🟥")

    def test_newest_row_level_wins_when_two_rows_name_one_session(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        with open(self.ledger, "w") as f:
            f.write(LEDGER.replace("| billing export lead [3fa9c1] | MANAGED", "| billing export lead [3fa9c1] | DONE (merged)\n"
                                   "| billing export lead [3fa9c1] | MANAGED"))
        self.assertEqual(self.guide_title(), "🟥🟥 Sessions Manager (1 managed · 1 watched · 0 active · 0 new) 🟥🟥")

    def test_done_sets_the_row_level_in_the_guide_ledger(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        before = open(self.ledger).read()
        r = self.run_script("done", "3fa9c100-0000-4000-8000-000000000000", CLAUDE_CODE_SESSION_ID=GUIDE)
        self.assertEqual(r.returncode, 0)
        self.assertIn("1 row(s)", r.stdout)
        self.assertEqual(open(self.ledger).read(),
                         before.replace("[3fa9c1] | MANAGED | billing lead", "[3fa9c1] | DONE | billing lead"))
        self.assertIn("(1 managed", self.guide_title())

    def test_done_without_a_findable_ledger_still_closes_and_says_so(self):
        r = self.run_script("done", WORKER)
        self.assertEqual(r.returncode, 0)
        self.assertIn("yourself", r.stdout)
        with open(os.path.join(self.cfg, "session-guide", "guides", WORKER)) as f:
            self.assertEqual(f.read(), "done\n")

    def job(self, sid, name, alive=False):
        """A job state.json for sid, and a sessions/<pid>.json that is alive (this test process) or dead."""
        d = os.path.join(self.cfg, "jobs", sid[:8])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "state.json"), "w") as f:
            json.dump({"state": "done", "name": name, "sessionId": sid, "intent": "keep"}, f)
        os.makedirs(os.path.join(self.cfg, "sessions"), exist_ok=True)
        with open(os.path.join(self.cfg, "sessions", "1.json"), "w") as f:
            json.dump({"pid": os.getpid() if alive else 2 ** 22 + 12345, "sessionId": sid}, f)
        return os.path.join(d, "state.json")

    def test_done_retitles_the_job_of_a_session_with_no_process(self):
        path = self.job(WORKER, "🟧🟧 (g) billing lead · Waiting on CI")
        self.run_script("guided", WORKER)
        r = self.run_script("done", WORKER)
        self.assertIn("state.json", r.stdout)
        state = json.load(open(path))
        self.assertEqual((state["name"], state["state"], state["intent"]), ("✅ billing lead · Waiting on CI", "done", "keep"))
        self.assertEqual(self.run_script("done", WORKER).returncode, 0)  # a repeat changes nothing
        self.assertEqual(json.load(open(path))["name"], "✅ billing lead · Waiting on CI")

    def test_done_leaves_the_job_of_a_live_session_to_its_next_prompt(self):
        path = self.job(WORKER, "🟧🟧 (g) billing lead", alive=True)
        r = self.run_script("done", WORKER)
        self.assertIn("next prompt", r.stdout)
        self.assertEqual(json.load(open(path))["name"], "🟧🟧 (g) billing lead")
        self.assertEqual(self.worker_title("🟧🟧 (g) billing lead"), "✅ billing lead")  # resumed: follows the marker

    def test_guide_prompt_renames_a_closed_session_once_its_process_has_ended(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        path = self.job(WORKER, "🟧🟧 (g) billing lead", alive=True)
        self.run_script("done", WORKER)  # the process is alive: nothing renamed yet
        self.assertEqual(json.load(open(path))["name"], "🟧🟧 (g) billing lead")
        context = json.loads(self.hook().stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("CLOSE message: " + WORKER[:8], context)
        self.assertIn("Held: [%s]" % WORKER[:8], self.run_script("sweep", CLAUDE_CODE_SESSION_ID=GUIDE).stdout)
        self.assertEqual(json.load(open(path))["name"], "🟧🟧 (g) billing lead")  # a live process is never edited
        self.job(WORKER, "🟧🟧 (g) billing lead")  # the process ended
        self.assertNotIn("CLOSE message", self.hook().stdout)
        self.assertEqual(json.load(open(path))["name"], "✅ billing lead")

    def test_a_held_session_with_a_plain_title_is_not_worth_a_message(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        path = self.job(WORKER, "billing lead", alive=True)
        self.run_script("done", WORKER)
        self.assertNotIn("Held", self.run_script("sweep", CLAUDE_CODE_SESSION_ID=GUIDE).stdout)
        self.assertEqual(json.load(open(path))["name"], "billing lead")
        self.job(WORKER, "billing lead")  # the process ended
        self.run_script("sweep", CLAUDE_CODE_SESSION_ID=GUIDE)
        self.assertEqual(json.load(open(path))["name"], "✅ billing lead")

    def test_sweep_renames_sessions_closed_before_done_could_rename(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        path = self.job(WORKER, "🟧🟧 (g) billing lead")
        with open(os.path.join(self.cfg, "session-guide", "guides", WORKER), "w") as f:
            f.write("done\n")
        self.assertNotIn("Held", self.run_script("sweep", CLAUDE_CODE_SESSION_ID=GUIDE).stdout)
        self.assertEqual(json.load(open(path))["name"], "✅ billing lead")

    def test_a_worker_prompt_settles_nothing(self):
        path = self.job(WORKER, "🟧🟧 (g) billing lead")
        os.makedirs(os.path.join(self.cfg, "session-guide", "guides"), exist_ok=True)
        with open(os.path.join(self.cfg, "session-guide", "guides", WORKER), "w") as f:
            f.write("done\n")
        self.hook(session_id=GUIDE)  # GUIDE has no marker here: not a guide
        self.assertEqual(json.load(open(path))["name"], "🟧🟧 (g) billing lead")

    def test_a_job_that_is_only_done_is_not_closed(self):
        path = self.job(WORKER, "🟧🟧 (g) billing lead")
        self.run_script("guided", WORKER)
        self.assertEqual(open(os.path.join(self.cfg, "session-guide", "guides", WORKER)).read(), "guided\n")
        self.assertEqual(json.load(open(path))["name"], "🟧🟧 (g) billing lead")

    def test_sweep_offers_sessions_whose_rows_are_all_done_but_still_marked(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        self.run_script("guided", "3fa9c100-0000-4000-8000-000000000000")
        self.run_script("guided", "a1a1a100-0000-4000-8000-000000000000")
        with open(self.ledger, "w") as f:
            f.write(LEDGER.replace("[3fa9c1] | MANAGED", "[3fa9c1] | DONE"))
        r = self.run_script("sweep", CLAUDE_CODE_SESSION_ID=GUIDE)
        self.assertIn("Closable: [3fa9c100]", r.stdout)
        self.assertNotIn("a1a1a100", r.stdout)
        self.assertIn("done <id>", json.loads(self.hook().stdout)["hookSpecificOutput"]["additionalContext"])
        self.run_script("done", "3fa9c100-0000-4000-8000-000000000000", CLAUDE_CODE_SESSION_ID=GUIDE)
        self.assertNotIn("Closable", self.run_script("sweep", CLAUDE_CODE_SESSION_ID=GUIDE).stdout)


if __name__ == "__main__":
    unittest.main()
