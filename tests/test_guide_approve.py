#!/usr/bin/env python3
"""Tests for skills/session-guide/scripts/guide_approve.py. Every test uses its own temp CLAUDE_CONFIG_DIR."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "session-guide", "scripts"))
import guide_approve as ga  # noqa: E402

CLEAN = {"HOME": "/x"}


class ApproveTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        p = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self.dir})
        p.start()
        self.addCleanup(p.stop)
        self.agent_list = []
        p = mock.patch.object(ga, "agents", lambda: self.agent_list)
        p.start()
        self.addCleanup(p.stop)

    def job(self, id8, name="worker one", result="All done here."):
        os.makedirs(os.path.join(self.dir, "jobs", id8))
        with open(os.path.join(self.dir, "jobs", id8, "state.json"), "w") as f:
            json.dump({"name": name, "state": "idle", "output": {"result": result}}, f)

    def run_main(self, argv, env=CLEAN, tty=True, answer="y"):
        out = io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch("sys.stdin") as stdin, \
                mock.patch("builtins.input", return_value=answer), \
                mock.patch.object(ga.subprocess, "run") as run, mock.patch.object(ga.os, "execvp") as ex:
            stdin.isatty.return_value = tty
            code = ga.main(argv, env)
        return code, out.getvalue(), run, ex

    def test_resolve_one_none_many(self):
        self.job("4208c0a8")
        self.job("4208ffff")
        self.assertEqual(list(ga.resolve("4208c0a8", [])), ["4208c0a8"])
        self.assertEqual(ga.resolve("9999", []), {})
        self.assertEqual(len(ga.resolve("4208", [])), 2)
        agent = {"sessionId": "4208c0a8-1111", "kind": "background", "name": "n"}
        self.assertEqual(list(ga.resolve("4208c0a8", [agent])), ["4208c0a8"])

    def test_no_match_and_many_refuse(self):
        code, out, run, ex = self.run_main(["abcd", "ok"])
        self.assertEqual(code, 1)
        self.assertIn("No background session", out)
        self.job("4208c0a8")
        self.job("4208ffff")
        code, out, run, ex = self.run_main(["4208", "ok"])
        self.assertEqual(code, 1)
        self.assertIn("matches 2", out)
        ex.assert_not_called()

    def test_prints_session(self):
        self.job("4208c0a8", result="x" * 400)
        self.agent_list = [{"sessionId": "4208c0a8-1", "kind": "background", "state": "blocked",
                            "waitingFor": "approval to push", "cwd": "/w"}]
        code, out, run, ex = self.run_main(["4208c0a8", "ok", "--no-attach"], env={"CLAUDECODE": "1"}, tty=False)
        self.assertEqual(code, 0)
        for s in ("worker one", "blocked", "approval to push", "/w", "x" * 300 + "..."):
            self.assertIn(s, out)
        ex.assert_not_called()

    def test_inside_claude_refuses(self):
        self.job("4208c0a8")
        for env in ({"CLAUDECODE": "1"}, {"CLAUDE_CODE_SESSION_ID": "abc"}):
            code, out, run, ex = self.run_main(["4208c0a8", "ok"], env=env)
            self.assertEqual(code, 1)
            self.assertIn("not with ! inside a Claude window", out)
            run.assert_not_called()
            ex.assert_not_called()

    def test_non_tty_refuses(self):
        self.job("4208c0a8")
        code, out, run, ex = self.run_main(["4208c0a8", "ok"], tty=False)
        self.assertEqual(code, 1)
        self.assertIn("not a terminal", out)
        ex.assert_not_called()

    def test_n_does_nothing(self):
        self.job("4208c0a8")
        code, out, run, ex = self.run_main(["4208c0a8", "ok"], answer="")
        self.assertEqual(code, 1)
        run.assert_not_called()
        ex.assert_not_called()

    def test_y_copies_then_attaches(self):
        self.job("4208c0a8")
        code, out, run, ex = self.run_main(["4208c0a8", "guard ok"])
        run.assert_called_once()
        self.assertEqual(run.call_args[0][0], ["pbcopy"])
        self.assertEqual(run.call_args[1]["input"], "guard ok")
        self.assertIn("Paste it (cmd+V) when the session opens, then Enter", out)
        ex.assert_called_once_with("claude", ["claude", "attach", "4208c0a8"])


if __name__ == "__main__":
    unittest.main()
