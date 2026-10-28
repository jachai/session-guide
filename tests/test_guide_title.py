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
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_SESSION_ID", "SESSION_GUIDE_TITLE")}
        env.update(CLAUDE_CONFIG_DIR=self.cfg, **extra_env)
        return subprocess.run([sys.executable, SCRIPT] + list(args), input=stdin, capture_output=True, text=True,
                              env=env)

    def hook(self, session_id=GUIDE, event="UserPromptSubmit"):
        return self.run_script("hook", stdin=json.dumps({"session_id": session_id, "hook_event_name": event}))

    def test_marked_session_gets_exact_title_with_counts(self):
        self.assertEqual(self.run_script("mark", self.ledger, "--session", GUIDE).returncode, 0)
        for event in ("UserPromptSubmit", "SessionStart"):
            r = self.hook(event=event)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout), {"hookSpecificOutput": {
                "hookEventName": event,
                "sessionTitle": "🟥🟥 Sessions Manager (2 of 3) 🟥🟥"}})

    def test_counts_follow_the_ledger(self):
        self.run_script("mark", self.ledger, "--session", GUIDE)
        with open(self.ledger, "w") as f:
            f.write(LEDGER.replace("| design spike [b5c6d7] | WATCHED", "| design spike [b5c6d7] | MANAGED"))
        self.assertIn("(3 of 3)", self.hook().stdout)

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
        self.assertIn("(2 of 3)", self.hook().stdout)


if __name__ == "__main__":
    unittest.main()
