#!/usr/bin/env python3
"""peek: what a Claude Code or Codex session last said and whether it is waiting on a question.

    python3 peek.py <id-prefix> [<id-prefix> ...] [--chars 900]
    python3 peek.py <id-prefix> --runtime claude|codex|auto
    python3 peek.py --version

Reads Claude transcripts from $CLAUDE_CONFIG_DIR (default ~/.claude) and Codex rollouts from $CODEX_HOME (default
~/.codex), read-only. Auto mode searches both and picks the newest matching session. Per session it prints the title
or Codex agent path, last write time, approximate context tokens, model and effort, last assistant text (truncated),
the latest structured user question and whether it was answered, and the last cross-session message it received.
Python 3 stdlib only.
"""
import glob
import json
import os
import sys
import time

__version__ = "0.1.15"


def claude_config_dir():
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return config


def codex_config_dir():
    return os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")


def find(prefix, runtime="auto"):
    hits = []
    if runtime in ("auto", "claude"):
        hits += [("claude", p) for p in glob.glob(
            os.path.join(claude_config_dir(), "projects", "*", "%s*.jsonl" % prefix))]
    if runtime in ("auto", "codex"):
        root = codex_config_dir()
        patterns = [os.path.join(root, "sessions", "*", "*", "*", "rollout-*-%s*.jsonl" % prefix),
                    os.path.join(root, "archived_sessions", "rollout-*-%s*.jsonl" % prefix)]
        for pattern in patterns:
            hits += [("codex", p) for p in glob.glob(pattern)]
    return max(hits, key=lambda hit: os.path.getmtime(hit[1])) if hits else (None, None)


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def peek_claude(path, chars):
    title, ctx, last_text, last_any, ask, answered, last_xmsg = "", 0, "", "", None, False, ""
    model, effort = "", ""
    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("customTitle"):
            title = d["customTitle"]
        m = d.get("message") or {}
        c = m.get("content")
        if d.get("type") == "api-request" and d.get("querySource") in (None, "repl_main_thread"):
            params = d.get("params") or {}
            model = params.get("model") or model
            effort = (params.get("output_config") or {}).get("effort") or effort
        if d.get("type") == "assistant" and not d.get("isSidechain"):
            if m.get("model") and not m["model"].startswith("<"):  # "<synthetic>" marks an error turn, not a model
                model = m["model"]
            effort = d.get("perTurnEffort") or effort
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
    print("=== %s [%s] · last write %s · ctx %dk · %s / %s" % (title or "(untitled)", sid, mt, ctx // 1000,
                                                             model or "model ?", effort or "effort ?"))
    if ask:
        print("ASKED (%s):" % ("answered" if answered else "WAITING ON AN ANSWER"))
        for q in ask:
            print("  - " + q[:400])
    last_text = last_text or last_any
    print("LAST TEXT: " + (last_text[:chars] + (" …" if len(last_text) > chars else "")).strip())
    if last_xmsg:
        print("LAST CROSS-SESSION MSG IN: " + last_xmsg[:300].replace("\n", " "))
    print()


def content_text(content, kinds=("input_text", "output_text")):
    return " ".join(part.get("text", "") for part in content or []
                    if isinstance(part, dict) and part.get("type") in kinds).strip()


def json_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def codex_index_title(session_id):
    path = os.path.join(codex_config_dir(), "session_index.jsonl")
    title = ""
    try:
        for line in open(path, errors="replace"):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("id") == session_id and row.get("thread_name"):
                title = row["thread_name"]
    except OSError:
        pass
    return title


def peek_codex(path, chars):
    """Read the stable, local Codex rollout fields; ignore unknown records so schema additions fail open."""
    session_id, title, agent_path, nickname = "", "", "", ""
    ctx, model, effort, last_text, last_any, last_xmsg = 0, "", "", "", "", ""
    ask, ask_call, answered = None, None, False
    for line in open(path, errors="replace"):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        payload = row.get("payload") or {}
        kind = row.get("type")
        if kind == "session_meta":
            session_id = payload.get("id") or session_id
            agent_path = payload.get("agent_path") or agent_path
            nickname = payload.get("agent_nickname") or nickname
        elif kind == "turn_context":
            model = payload.get("model") or model
            effort = payload.get("effort") or effort
        elif kind == "token_usage_record":
            usage = payload.get("usage") or {}
            ctx = usage.get("input_tokens") or ctx
        elif kind == "response_item":
            item_type = payload.get("type")
            if item_type == "message" and payload.get("role") == "assistant":
                text = content_text(payload.get("content"), ("output_text",))
                if text:
                    last_any = text
                    if len(text) > 200:
                        last_text, ask, ask_call, answered = text, None, None, False
            elif item_type in ("function_call", "custom_tool_call") and \
                    payload.get("name") == "request_user_input":
                data = json_object(payload.get("arguments") or payload.get("input"))
                questions = data.get("questions") or []
                ask = [q.get("question", "") for q in questions if isinstance(q, dict) and q.get("question")]
                ask_call, answered = payload.get("call_id"), False
            elif item_type in ("function_call_output", "custom_tool_call_output") and \
                    ask_call and payload.get("call_id") == ask_call:
                answered = True
            elif item_type == "agent_message":
                recipient = payload.get("recipient") or ""
                text = content_text(payload.get("content"), ("input_text", "output_text"))
                if text and (not agent_path or recipient == agent_path):
                    last_xmsg = text
    title = agent_path or nickname or codex_index_title(session_id)
    sid = (session_id or os.path.basename(path).rsplit("-", 5)[-5])[:8]
    mt = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    print("=== %s [%s] · codex · last write %s · ctx %dk · %s / %s" %
          (title or "(untitled)", sid, mt, ctx // 1000, model or "model ?", effort or "effort ?"))
    if ask:
        print("ASKED (%s):" % ("answered" if answered else "WAITING ON AN ANSWER"))
        for question in ask:
            print("  - " + question[:400])
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
    runtime = os.environ.get("SESSION_GUIDE_RUNTIME", "auto").lower()
    if "--runtime" in argv:
        i = argv.index("--runtime")
        runtime = argv[i + 1].lower()
        argv = argv[:i] + argv[i + 2:]
    if runtime not in ("auto", "claude", "codex"):
        print("runtime is one of: auto, claude, codex", file=sys.stderr)
        return 2
    if not argv:
        print(__doc__)
        return 2
    for prefix in argv:
        found_runtime, path = find(prefix, runtime)
        if path:
            (peek_codex if found_runtime == "codex" else peek_claude)(path, chars)
        else:
            print("=== [%s] no transcript found\n" % prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
