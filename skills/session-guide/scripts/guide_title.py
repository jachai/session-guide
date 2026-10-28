#!/usr/bin/env python3
"""guide_title: keep the guide session's title pinned, with live counts from its ledger.

    python3 guide_title.py mark <ledger.md> [--session <id>]   this session is a guide
    python3 guide_title.py unmark [--session <id>]             it no longer is
    python3 guide_title.py retire [<id>]                       it handed over: green title, never red again
    python3 guide_title.py hook                                UserPromptSubmit / SessionStart hook (JSON on stdin)

A marked session gets this title on every prompt and every start, so a rename (by hand or by another titling hook)
is undone on the next turn:

    🟥🟥 Sessions Manager (X of Y) 🟥🟥

X = MANAGED rows and Y = MANAGED + WATCHED rows in the ledger's `## Sessions` table. To pick your own format, set
SESSION_GUIDE_TITLE (for hooks: in settings.json "env") with {managed} and {active} placeholders. Avoid `*` and keep
it under ~35 characters: some title tools strip markdown and the agents view truncates. The marker is
$CLAUDE_CONFIG_DIR/session-guide/guides/<session id> (default ~/.claude), holding the ledger path. The hook fails
open: an unmarked session, a missing or unreadable ledger, or bad input prints nothing and exits 0.

A retired guide (one that handed over to a new guide) gets RETIRED_TITLE instead, on its next prompt and from then on
(override: SESSION_GUIDE_RETIRED_TITLE). Its marker holds `retired`, so the hook can't turn it red again.
--session (and retire's <id>) defaults to $CLAUDE_CODE_SESSION_ID and may be an id prefix. Python 3 stdlib only.
"""
import argparse
import glob
import json
import os
import sys

TITLE = "\U0001f7e5\U0001f7e5 Sessions Manager ({managed} of {active}) \U0001f7e5\U0001f7e5"
RETIRED_TITLE = "\U0001f7e9\U0001f7e9 Sessions Manager (retired) \U0001f7e9\U0001f7e9"
RETIRED = "retired"  # marker content for a retired guide, in place of a ledger path


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def marker(session_id):
    return os.path.join(config_dir(), "session-guide", "guides", session_id)


def resolve_session(given):
    sid = given or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not sid:
        raise SystemExit("no session id: pass --session <id>")
    if len(sid) == 36:
        return sid
    hits = {os.path.basename(p)[:-6] for p in glob.glob(os.path.join(config_dir(), "projects", "*", sid + "*.jsonl"))}
    if len(hits) != 1:
        raise SystemExit("--session %s matches %d sessions; pass the full id" % (sid, len(hits)))
    return hits.pop()


def counts(ledger):
    """(managed, active) from the ledger's ## Sessions table, or None when there is no such table."""
    managed = watched = 0
    in_sessions = seen = False
    for line in open(ledger, errors="replace"):
        if line.startswith("## "):
            in_sessions = line.strip() == "## Sessions"
            continue
        if not in_sessions or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        seen = True
        level = cells[1].split()[0] if cells[1] else ""
        managed += level == "MANAGED"
        watched += level == "WATCHED"
    return (managed, managed + watched) if seen else None


def title_for(session_id):
    path = marker(session_id)
    if not os.path.isfile(path):
        return None
    content = open(path).read().strip()
    if content == RETIRED:
        return os.environ.get("SESSION_GUIDE_RETIRED_TITLE") or RETIRED_TITLE
    ledger = os.path.expanduser(content)
    found = counts(ledger)
    if found is None:
        return None
    return (os.environ.get("SESSION_GUIDE_TITLE") or TITLE).format(managed=found[0], active=found[1])


def cmd_hook():
    try:
        event = json.load(sys.stdin)
        title = title_for(event["session_id"])
        if title:
            json.dump({"hookSpecificOutput": {"hookEventName": event.get("hook_event_name", "UserPromptSubmit"),
                                              "sessionTitle": title}}, sys.stdout)  # ASCII-escaped: any locale
    except Exception:  # fail open: a broken guide title must never block a prompt
        pass
    return 0


def cmd_mark(args):
    sid = resolve_session(args.session)
    ledger = os.path.abspath(os.path.expanduser(args.ledger))
    if counts(ledger) is None:
        raise SystemExit("%s has no ## Sessions table" % ledger)
    if os.path.isfile(marker(sid)) and open(marker(sid)).read().strip() == RETIRED:
        raise SystemExit("%s is a retired guide; a new guide needs a fresh session" % sid[:8])
    os.makedirs(os.path.dirname(marker(sid)), exist_ok=True)
    with open(marker(sid), "w") as f:
        f.write(ledger + "\n")
    print("%s is a guide; title from its next prompt: %s" % (sid[:8], title_for(sid)))
    return 0


def cmd_unmark(args):
    sid = resolve_session(args.session)
    if os.path.exists(marker(sid)):
        os.remove(marker(sid))
        print("%s is no longer a guide; its title is left as it is" % sid[:8])
    else:
        print("%s was not marked" % sid[:8])
    return 0


def cmd_retire(args):
    sid = resolve_session(args.session)
    os.makedirs(os.path.dirname(marker(sid)), exist_ok=True)
    with open(marker(sid), "w") as f:
        f.write(RETIRED + "\n")
    print("%s is retired; title from its next prompt: %s" % (sid[:8], title_for(sid)))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Pin the guide session's title.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook", help="run as a UserPromptSubmit / SessionStart hook")
    mark = sub.add_parser("mark", help="mark a session as the guide of a ledger")
    mark.add_argument("ledger")
    mark.add_argument("--session")
    unmark = sub.add_parser("unmark", help="unmark a guide session")
    unmark.add_argument("--session")
    retire = sub.add_parser("retire", help="retire a guide that handed over (green title)")
    retire.add_argument("session", nargs="?")
    args = p.parse_args(argv)
    commands = {"hook": lambda a: cmd_hook(), "mark": cmd_mark, "unmark": cmd_unmark, "retire": cmd_retire}
    return commands[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
