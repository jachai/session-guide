#!/usr/bin/env python3
"""guide_title: keep the guide session's title pinned, with live counts from its ledger, and mark guided workers.

    python3 guide_title.py mark <ledger.md> [--session <id>]   this session is a guide
    python3 guide_title.py unmark [--session <id>]             it no longer is
    python3 guide_title.py retire [<id>]                       it handed over: green title, never red again
    python3 guide_title.py guided [<id>]                       a MANAGED worker: "(g) " before its title
    python3 guide_title.py unguided [<id>]                     no longer managed: the prefix comes off
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

A guided worker (marker `guided`) keeps its own title with GUIDED_PREFIX in front (override:
SESSION_GUIDE_GUIDED_PREFIX), so the user can tell at a glance which sessions don't need them. The hook prefixes the
title the session has now and prints nothing once it is prefixed, so another titling hook (session-titles) sees a
rename, adopts the prefixed origin and keeps it through focus updates. Repeated prefixes collapse to one. `unguided`
(marker `unguided`) takes the prefix off on the next prompt, after which the hook drops the marker. A guide or a
retired guide is never prefixed: `guided` refuses them, and `mark` replaces a guided marker.
--session (and the <id> of retire / guided / unguided) defaults to $CLAUDE_CODE_SESSION_ID and may be an id prefix.
Python 3 stdlib only.
"""
import argparse
import glob
import json
import os
import sys

TITLE = "\U0001f7e5\U0001f7e5 Sessions Manager ({managed} of {active}) \U0001f7e5\U0001f7e5"
RETIRED_TITLE = "\U0001f7e9\U0001f7e9 Sessions Manager (retired) \U0001f7e9\U0001f7e9"
GUIDED_PREFIX = "(g) "
RETIRED = "retired"  # marker content for a retired guide, in place of a ledger path
GUIDED, UNGUIDED = "guided", "unguided"  # marker content for a MANAGED worker, and for one that just left


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def marker(session_id):
    return os.path.join(config_dir(), "session-guide", "guides", session_id)


def resolve_session(given):
    """A full session id from `given` (an id or id prefix), or this session's own id when no id was passed at all.

    An empty id (say, from a failed lookup) is an error, never this session. A prefix is looked up in every project
    folder, worktree folders included, since a worker that ran EnterWorktree keeps its transcript there.
    """
    sid = (os.environ.get("CLAUDE_CODE_SESSION_ID", "") if given is None else given).strip()
    if not sid:
        raise SystemExit("empty session id" if given is not None else "no session id: pass one")
    if len(sid) == 36:
        return sid
    hits = {os.path.basename(p)[:-6] for p in glob.glob(os.path.join(config_dir(), "projects", "*", sid + "*.jsonl"))}
    if len(hits) != 1:
        raise SystemExit("session %s matches %d sessions; pass the full id" % (sid, len(hits)))
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


def marker_content(session_id):
    path = marker(session_id)
    return open(path).read().strip() if os.path.isfile(path) else None


def guided_prefix():
    return os.environ.get("SESSION_GUIDE_GUIDED_PREFIX") or GUIDED_PREFIX


def worker_title(content, current):
    """The guided / unguided title for `current`, or None when it is already right (or there is none yet)."""
    bare, mark = current, guided_prefix().strip()
    while mark and bare.startswith(mark):
        bare = bare[len(mark):].lstrip()
    want = guided_prefix() + bare if content == GUIDED else bare
    return want if bare and want != current else None


def title_for(session_id, current=""):
    content = marker_content(session_id)
    if content is None:
        return None
    if content in (GUIDED, UNGUIDED):
        return worker_title(content, current)
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
        sid = event["session_id"]
        current = (event.get("session_title") or "").strip()
        title = title_for(sid, current)
        if marker_content(sid) == UNGUIDED and current and not title:
            os.remove(marker(sid))  # the prefix is off: nothing left to undo
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
    write_marker(sid, ledger)
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
    write_marker(sid, RETIRED)
    print("%s is retired; title from its next prompt: %s" % (sid[:8], title_for(sid)))
    return 0


def cmd_guided(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content not in (None, GUIDED, UNGUIDED):
        raise SystemExit("%s is a guide%s; guides get no prefix" % (sid[:8], " (retired)" * (content == RETIRED)))
    write_marker(sid, GUIDED)
    print("%s is guided; %r goes before its title from its next prompt" % (sid[:8], guided_prefix()))
    return 0


def cmd_unguided(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content not in (None, GUIDED, UNGUIDED):
        print("%s is a guide, not a guided worker; left as it is" % sid[:8])
        return 0
    write_marker(sid, UNGUIDED)
    print("%s is unguided; the prefix comes off its title on its next prompt" % sid[:8])
    return 0


def write_marker(session_id, content):
    os.makedirs(os.path.dirname(marker(session_id)), exist_ok=True)
    with open(marker(session_id), "w") as f:
        f.write(content + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description="Pin the guide session's title and mark guided workers.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook", help="run as a UserPromptSubmit / SessionStart hook")
    mark = sub.add_parser("mark", help="mark a session as the guide of a ledger")
    mark.add_argument("ledger")
    mark.add_argument("--session")
    unmark = sub.add_parser("unmark", help="unmark a guide session")
    unmark.add_argument("--session")
    retire = sub.add_parser("retire", help="retire a guide that handed over (green title)")
    retire.add_argument("session", nargs="?")
    guided = sub.add_parser("guided", help='a MANAGED worker: "(g) " before its title')
    guided.add_argument("session", nargs="?")
    unguided = sub.add_parser("unguided", help="no longer managed: the prefix comes off")
    unguided.add_argument("session", nargs="?")
    args = p.parse_args(argv)
    commands = {"hook": lambda a: cmd_hook(), "mark": cmd_mark, "unmark": cmd_unmark, "retire": cmd_retire,
                "guided": cmd_guided, "unguided": cmd_unguided}
    return commands[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
