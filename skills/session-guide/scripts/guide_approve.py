#!/usr/bin/env python3
"""guide_approve: attach to a background session in a NEW terminal tab with the user's approval on the clipboard.

    python3 guide_approve.py <id8> "<approval text>" [--no-attach]

Run it in a plain terminal, never with ! inside a Claude window (`!` cannot switch windows). It resolves <id8> to
exactly one background session (~/.claude/jobs/<id8>/state.json and `claude agents --json --all`), shows its title,
state, what it waits for, its cwd and its last assistant text, asks for a y, copies the approval to the clipboard
(pbcopy) and runs `claude attach <id8>`. It never sends the approval: the user pastes it and presses Enter.
--no-attach only prints the session (a dry run; works without a TTY).
Python 3 stdlib only.
"""
import glob
import json
import os
import subprocess
import sys

__version__ = "0.1.17"
WRONG_PLACE = ("Run this in a new terminal tab, not with ! inside a Claude window: `!` cannot switch windows.")


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def agents():
    try:
        out = subprocess.run(["claude", "agents", "--json", "--all"], capture_output=True, text=True, timeout=60).stdout
        data = json.loads(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    if isinstance(data, dict):
        data = data.get("agents") or []
    return [a for a in data if isinstance(a, dict)]


def load_state(id8):
    try:
        with open(os.path.join(config_dir(), "jobs", id8, "state.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def resolve(prefix, agent_list):
    """Every distinct background session whose id starts with prefix: {id8: {"id8", "agent", "state"}}."""
    found = {}
    for d in glob.glob(os.path.join(config_dir(), "jobs", prefix + "*")):
        if os.path.isdir(d):
            found.setdefault(os.path.basename(d)[:8], {})
    for a in agent_list:
        sid = a.get("sessionId") or a.get("id") or ""
        if sid.startswith(prefix) and a.get("kind", "background") == "background":
            found.setdefault(sid[:8], {})["agent"] = a
    out = {}
    for id8, info in found.items():
        info["id8"] = id8
        info["state"] = load_state(id8)
        out[id8] = info
    return out


def last_assistant_text(id8, state):
    hits = glob.glob(os.path.join(config_dir(), "projects", "*", id8 + "*.jsonl"))
    if hits:
        text = ""
        for line in open(max(hits, key=os.path.getmtime), errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") != "assistant" or d.get("isSidechain"):
                continue
            c = (d.get("message") or {}).get("content")
            t = c if isinstance(c, str) else " ".join(
                b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text")
            if t.strip():
                text = t.strip()
        if text:
            return text
    out = state.get("output")
    return ((out.get("result") if isinstance(out, dict) else out) or state.get("detail") or "").strip()


def describe(info):
    a, st = info.get("agent") or {}, info["state"]
    title = st.get("name") or a.get("name") or "(untitled)"
    lines = ["Session: %s [%s]" % (title, info["id8"]),
             "State:   %s" % (a.get("state") or st.get("state") or "unknown")]
    if a.get("waitingFor"):
        lines.append("Waiting: %s" % a["waitingFor"])
    lines.append("Cwd:     %s" % (a.get("cwd") or st.get("cwd") or "unknown"))
    last = " ".join(last_assistant_text(info["id8"], st).split())
    lines.append("Last:    %s" % (last[:300] + ("..." if len(last) > 300 else "") if last else "(nothing found)"))
    return title, "\n".join(lines)


def inside_claude(env):
    return env.get("CLAUDECODE") == "1" or any(k.startswith("CLAUDE_CODE_") for k in env)


def main(argv=None, env=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if env is None else env
    no_attach = "--no-attach" in argv
    args = [a for a in argv if a != "--no-attach"]
    if len(args) != 2:
        print(__doc__.split("\n\n")[0] + "\n\nusage: guide_approve.py <id8> \"<approval text>\" [--no-attach]")
        return 2
    prefix, approval = args
    found = resolve(prefix, agents())
    if not found:
        print("No background session matches %r." % prefix)
        return 1
    if len(found) > 1:
        print("%r matches %d sessions; use a longer id:" % (prefix, len(found)))
        for id8, info in sorted(found.items()):
            print("  %s  %s" % (id8, describe(info)[0]))
        return 1
    info = next(iter(found.values()))
    title, text = describe(info)
    print(text)
    id8 = info["id8"]
    if no_attach:
        print("\n--no-attach: nothing copied, nothing attached. Approval would be: %s" % approval)
        return 0
    if inside_claude(env):
        print("\n" + WRONG_PLACE)
        return 1
    if not sys.stdin.isatty():
        print("\nstdin is not a terminal. " + WRONG_PLACE)
        return 1
    if input("\nAttach to '%s' [%s] and paste the approval? [y/N] " % (title, id8)).strip().lower() != "y":
        print("Not attaching.")
        return 1
    subprocess.run(["pbcopy"], input=approval, text=True, check=True)
    print("Paste it (cmd+V) when the session opens, then Enter.")
    sys.stdout.flush()
    os.execvp("claude", ["claude", "attach", id8])


if __name__ == "__main__":
    sys.exit(main())
