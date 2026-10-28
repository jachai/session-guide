#!/usr/bin/env python3
"""Run peek.py on made-up sessions in a temp config dir. Nothing touches your real ~/.claude.

    python3 scripts/demo.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEEK = os.path.join(ROOT, "skills", "session-guide", "scripts", "peek.py")

SESSIONS = [
    ("3fa9c1d2", "billing export lead · PR 142 green, awaiting merge", 141000,
     "PR #142 (billing export, develop copy) is green at a1b2c3d: full suite passed in 11m21s and the rounding fix "
     "holds on all 64 battery checks I can run locally. Next: you merge #142, staging deploys, then the regression "
     "battery. I'm at 71% context and will hand off after the staging verdict.", None, None),
    ("b5c6d7e8", "search reindex worker · Waiting on a refund rule", 88000,
     "The reindex is done on staging, but one rule needs a decision before I write the backfill. Details below.",
     ["Partial refund on a 3-item order (600.00), customer returns 1 item (200.00), store at fault: refund the "
      "5.00 restocking fee too?"], None),
    ("e8f9a0b1", "release guide · Waiting on #142 merge", 64000,
     "Needs you now: 1. Merge #142 (green, mergeable, no deploy running). Streams: billing export → staging gate; "
     "search reindex → refund rule pending; docs refresh DONE.", None,
     '<cross-session-message from="uds:/tmp/cc-socks/41.sock">PR #142 green at a1b2c3d</cross-session-message>'),
]


def main():
    cfg = tempfile.mkdtemp(prefix="session-guide-demo-")
    proj = os.path.join(cfg, "projects", "-home-you-repo")
    os.makedirs(proj)
    try:
        for sid, title, ctx, text, ask, xmsg in SESSIONS:
            rows = [{"customTitle": title}]
            if xmsg:
                rows.append({"type": "user", "message": {"content": xmsg}})
            content = [{"type": "text", "text": text}]
            if ask:
                content.append({"type": "tool_use", "name": "AskUserQuestion",
                                "input": {"questions": [{"question": q, "options": []} for q in ask]}})
            rows.append({"type": "assistant", "message": {"content": content,
                                                          "usage": {"input_tokens": 2, "cache_read_input_tokens": ctx}}})
            with open(os.path.join(proj, sid + "-demo.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(r) for r in rows) + "\n")
        env = dict(os.environ, CLAUDE_CONFIG_DIR=cfg)
        cmd = [sys.executable, PEEK, "--chars", "220"] + [s[0] for s in SESSIONS]
        print("$ python3 peek.py --chars 220 3fa9c1d2 b5c6d7e8 e8f9a0b1\n")
        sys.stdout.flush()
        return subprocess.call(cmd, env=env)
    finally:
        shutil.rmtree(cfg)


if __name__ == "__main__":
    sys.exit(main())
