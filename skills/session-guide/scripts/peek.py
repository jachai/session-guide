#!/usr/bin/env python3
"""peek: what a Claude Code session last said, whether it is waiting on a question, and how full it is.

    python3 peek.py <id-prefix> [<id-prefix> ...] [--chars 900]
    python3 peek.py --version

Reads $CLAUDE_CONFIG_DIR/projects/*/<id>*.jsonl (default ~/.claude), read-only. Per session prints:
  title (latest customTitle), last write time, context tokens of the last turn,
  the last long assistant text (truncated), any AskUserQuestion asked AFTER that text and whether it was answered,
  and the last cross-session message it received.
Python 3 stdlib only.
"""
import glob
import json
import os
import sys
import time

__version__ = "0.1.2"


def find(prefix):
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    hits = glob.glob(os.path.join(config, "projects", "*", "%s*.jsonl" % prefix))
    return max(hits, key=os.path.getmtime) if hits else None


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def peek(path, chars):
    title, ctx, last_text, last_any, ask, answered, last_xmsg = "", 0, "", "", None, False, ""
    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("customTitle"):
            title = d["customTitle"]
        m = d.get("message") or {}
        c = m.get("content")
        if d.get("type") == "assistant" and not d.get("isSidechain"):
            u = m.get("usage") or {}
            tok = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            if tok:
                ctx = tok
            for b in c or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b["text"].strip():
                    last_any = b["text"]
                    if len(b["text"]) > 200:  # a real reply, not a one-line aside; it supersedes earlier questions
                        last_text, ask, answered = b["text"], None, False
                if b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                    ask = [q.get("question", "") for q in b.get("input", {}).get("questions", [])]
                    answered = False
        elif d.get("type") == "user":
            s = text_of(c)
            if "<cross-session-message" in s:
                last_xmsg = s
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        r = b.get("content")
                        r = r if isinstance(r, str) else text_of(r)
                        if "have been answered" in r:
                            answered = True
    mt = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    sid = os.path.basename(path)[:8]
    print("=== %s [%s] · last write %s · ctx %dk" % (title or "(untitled)", sid, mt, ctx // 1000))
    if ask:
        print("ASKED (%s):" % ("answered" if answered else "WAITING ON AN ANSWER"))
        for q in ask:
            print("  - " + q[:400])
    last_text = last_text or last_any
    print("LAST TEXT: " + (last_text[:chars] + (" …" if len(last_text) > chars else "")).strip())
    if last_xmsg:
        print("LAST CROSS-SESSION MSG IN: " + last_xmsg[:300].replace("\n", " "))
    print()


def main(argv):
    if "--version" in argv:
        print("peek %s" % __version__)
        return 0
    chars = 900
    if "--chars" in argv:
        i = argv.index("--chars")
        chars = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__)
        return 2
    for prefix in argv:
        path = find(prefix)
        if path:
            peek(path, chars)
        else:
            print("=== [%s] no transcript found\n" % prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
