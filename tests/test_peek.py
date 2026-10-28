#!/usr/bin/env python3
"""Tests for skills/session-guide/scripts/peek.py. Every test uses its own temp CLAUDE_CONFIG_DIR."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEEK = os.path.join(ROOT, "skills", "session-guide", "scripts", "peek.py")
LONG = "Billing export wave two is pushed and CI is green. " * 6


def assistant(text=None, ask=None, ctx=120000, sidechain=False):
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if ask:
        content.append({"type": "tool_use", "name": "AskUserQuestion",
                        "input": {"questions": [{"question": q, "options": []} for q in ask]}})
    return {"type": "assistant", "isSidechain": sidechain,
            "message": {"content": content, "usage": {"input_tokens": 2, "cache_read_input_tokens": ctx - 2}}}


def user(text=None, tool_result=None):
    if tool_result is not None:
        return {"type": "user", "message": {"content": [{"type": "tool_result", "content": tool_result}]}}
    return {"type": "user", "message": {"content": text}}


class PeekTest(unittest.TestCase):
    def setUp(self):
        self.cfg = tempfile.mkdtemp(prefix="peek-")
        self.proj = os.path.join(self.cfg, "projects", "-tmp-repo")
        os.makedirs(self.proj)

    def tearDown(self):
        shutil.rmtree(self.cfg)

    def write(self, sid, rows):
        with open(os.path.join(self.proj, sid + "-0000-0000-0000-000000000000.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def peek(self, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.cfg)
        p = subprocess.run([sys.executable, PEEK] + list(args), env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_title_ctx_and_last_text(self):
        self.write("a1b2c3d4", [{"customTitle": "billing export lead"}, assistant("short"), assistant(LONG, ctx=150000)])
        out = self.peek("a1b2c3d4")
        self.assertIn("billing export lead [a1b2c3d4]", out)
        self.assertIn("ctx 150k", out)
        self.assertIn("LAST TEXT: Billing export wave two", out)

    def test_unanswered_question_is_flagged(self):
        self.write("b2c3d4e5", [assistant(LONG), assistant(ask=["Refund the fee too?"])])
        out = self.peek("b2c3d4e5")
        self.assertIn("WAITING ON AN ANSWER", out)
        self.assertIn("Refund the fee too?", out)

    def test_answered_question_and_newer_text_clear_it(self):
        self.write("c3d4e5f6", [assistant(ask=["Q?"]), user(tool_result="Your questions have been answered: ...")])
        self.assertIn("ASKED (answered)", self.peek("c3d4e5f6"))
        self.write("d4e5f6a7", [assistant(ask=["Q?"]), assistant(LONG)])
        self.assertNotIn("ASKED", self.peek("d4e5f6a7"))

    def test_short_last_text_is_shown_when_no_long_one(self):
        self.write("a7b8c9d0", [assistant("Merged; watching the deploy.")])
        self.assertIn("LAST TEXT: Merged; watching the deploy.", self.peek("a7b8c9d0"))

    def test_sidechain_turns_do_not_set_ctx(self):
        self.write("e5f6a7b8", [assistant(LONG, ctx=90000), assistant(LONG, ctx=10000, sidechain=True)])
        self.assertIn("ctx 90k", self.peek("e5f6a7b8"))

    def test_cross_session_message_and_missing_and_chars(self):
        self.write("f6a7b8c9", [assistant(LONG), user('<cross-session-message from="uds:x">GO: merged</cross-session-message>')])
        out = self.peek("f6a7b8c9", "nope0000", "--chars", "40")
        self.assertIn("LAST CROSS-SESSION MSG IN", out)
        self.assertIn("[nope0000] no transcript found", out)
        self.assertIn(" …", out)

    def test_version_and_usage(self):
        self.assertRegex(self.peek("--version"), r"^peek \d+\.\d+\.\d+")
        p = subprocess.run([sys.executable, PEEK], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
