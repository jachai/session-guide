#!/usr/bin/env python3
"""Tests for the Claude and Codex transcript backends. Every test uses isolated config dirs."""
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
        self.codex = os.path.join(self.cfg, "codex")
        self.rollouts = os.path.join(self.codex, "sessions", "2026", "11", "04")
        os.makedirs(self.rollouts)

    def tearDown(self):
        shutil.rmtree(self.cfg)

    def write(self, sid, rows):
        with open(os.path.join(self.proj, sid + "-0000-0000-0000-000000000000.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def peek(self, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.cfg, CODEX_HOME=self.codex)
        p = subprocess.run([sys.executable, PEEK] + list(args), env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def write_codex(self, sid, rows, title=None):
        path = os.path.join(self.rollouts, "rollout-2026-11-04T12-00-00-%s.jsonl" % sid)
        with open(path, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        if title:
            with open(os.path.join(self.codex, "session_index.jsonl"), "a") as f:
                f.write(json.dumps({"id": sid, "thread_name": title, "updated_at": "2026-11-04T12:00:00Z"}) + "\n")

    @staticmethod
    def codex_row(kind, payload):
        return {"timestamp": "2026-11-04T12:00:00Z", "type": kind, "payload": payload}

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

    def test_model_and_effort_of_the_last_main_thread_turn(self):
        def request(model, effort, source="repl_main_thread"):
            return {"type": "api-request", "querySource": source,
                    "params": {"model": model, "output_config": {"effort": effort}}}
        turn = assistant(LONG)
        turn["message"]["model"], turn["perTurnEffort"] = "claude-sonnet-5-5", "low"
        error = assistant("API error")
        error["message"]["model"] = "<synthetic>"
        self.write("a7b8c9d0", [request("claude-opus-5-5", "high"), assistant(LONG), turn, error,
                                request("claude-haiku-5-5", "max", source="agent:custom")])
        self.assertIn("· claude-sonnet-5-5 / low", self.peek("a7b8c9d0"))
        self.write("b8c9d0e1", [request("claude-opus-5-5", "xhigh"), assistant(LONG)])
        self.assertIn("· claude-opus-5-5 / xhigh", self.peek("b8c9d0e1"))
        self.write("c9d0e1f2", [assistant(LONG)])
        self.assertIn("· model ? / effort ?", self.peek("c9d0e1f2"))

    def test_cross_session_message_and_missing_and_chars(self):
        self.write("f6a7b8c9", [assistant(LONG), user('<cross-session-message from="uds:x">GO: merged</cross-session-message>')])
        out = self.peek("f6a7b8c9", "nope0000", "--chars", "40")
        self.assertIn("LAST CROSS-SESSION MSG IN", out)
        self.assertIn("[nope0000] no transcript found", out)
        self.assertIn(" …", out)

    def test_codex_agent_path_context_model_and_last_text(self):
        sid = "01a1a7b9-f010-7b82-964b-6af748296148"
        rows = [
            self.codex_row("session_meta", {"id": sid, "agent_path": "/root/billing", "agent_nickname": "Ada"}),
            self.codex_row("turn_context", {"model": "gpt-test-sol", "effort": "high"}),
            self.codex_row("response_item", {"type": "message", "role": "assistant",
                                               "content": [{"type": "output_text", "text": LONG}]}),
            self.codex_row("token_usage_record", {"usage": {"input_tokens": 135000}}),
        ]
        self.write_codex(sid, rows)
        out = self.peek(sid[:8], "--runtime", "codex")
        self.assertIn("/root/billing [01a1a7b9] · codex", out)
        self.assertIn("ctx 135k", out)
        self.assertIn("gpt-test-sol / high", out)
        self.assertIn("LAST TEXT: Billing export wave two", out)

    def test_codex_question_answer_and_inbound_agent_message(self):
        sid = "01a1a7ba-f010-7b82-964b-6af748296148"
        call = {"type": "function_call", "name": "request_user_input", "call_id": "call-1",
                "arguments": json.dumps({"questions": [{"question": "Refund the fee too?"}]})}
        rows = [
            self.codex_row("session_meta", {"id": sid, "agent_path": "/root/refunds"}),
            self.codex_row("response_item", call),
            self.codex_row("response_item", {"type": "function_call_output", "call_id": "call-1", "output": "yes"}),
            self.codex_row("response_item", {"type": "agent_message", "author": "/root",
                                               "recipient": "/root/refunds",
                                               "content": [{"type": "input_text", "text": "Decision 3 FINAL: yes"}]}),
        ]
        self.write_codex(sid, rows)
        out = self.peek(sid[:8], "--runtime", "codex")
        self.assertIn("ASKED (answered)", out)
        self.assertIn("Refund the fee too?", out)
        self.assertIn("LAST CROSS-SESSION MSG IN: Decision 3 FINAL: yes", out)

    def test_codex_index_title_fallback_and_auto_detection(self):
        sid = "01a1a7bb-f010-7b82-964b-6af748296148"
        rows = [self.codex_row("session_meta", {"id": sid}),
                self.codex_row("response_item", {"type": "message", "role": "assistant",
                                                   "content": [{"type": "output_text", "text": "Finished."}]})]
        self.write_codex(sid, rows, title="release check")
        self.assertIn("release check [01a1a7bb] · codex", self.peek(sid[:8]))

    def test_version_and_usage(self):
        self.assertRegex(self.peek("--version"), r"^peek \d+\.\d+\.\d+")
        p = subprocess.run([sys.executable, PEEK], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
