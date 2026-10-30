#!/usr/bin/env python3
"""guide_title: keep the guide session's title pinned, with live counts from its ledger, and mark guided workers.

    python3 guide_title.py mark <ledger.md> [--session <id>]   this session is a guide
    python3 guide_title.py unmark [--session <id>]             it no longer is
    python3 guide_title.py retire [<id>]                       it handed over: faded red title, never red again
    python3 guide_title.py guided [<id>]                       a MANAGED worker: orange blocks + "(g) " first
    python3 guide_title.py watched [<id>]                      a WATCHED session: light gray blocks first
    python3 guide_title.py unguided [<id>]                     no longer managed or watched: the prefix comes off
    python3 guide_title.py unwatched [<id>]                    the same as unguided
    python3 guide_title.py done [<id>]                         closed: "✅ " before its title, never orange again
    python3 guide_title.py hook                                UserPromptSubmit / SessionStart hook (JSON on stdin)

A marked session gets this title on every prompt and every start, so a rename (by hand or by another titling hook)
is undone on the next turn:

    🟥🟥 Sessions Manager (2 managed · 1 watched · 3 new) 🟥🟥

managed and watched count the MANAGED and WATCHED rows in the ledger's `## Sessions` table; new is the guide's own
count of untracked sessions active in the last 12 hours, from a `New: <n>` line in the ledger header (0 when there is
none). To pick your own format, set SESSION_GUIDE_TITLE (for hooks: in settings.json "env") with {managed},
{watched}, {new} and {active} (managed + watched) placeholders. Avoid `*`: some title tools strip markdown. Keep
the "🟥🟥 Sessions Manager" start if you use claude-top: it falls back to it for a session without a marker. The
marker is
$CLAUDE_CONFIG_DIR/session-guide/guides/<session id> (default ~/.claude), holding the ledger path. The hook fails
open: an unmarked session, a missing or unreadable ledger, or bad input prints nothing and exits 0.

Every title kind has its own color, so the agents view reads at a glance:

    🟥🟥 Sessions Manager (...) 🟥🟥              the active guide
    🎟️🎟️ Sessions Manager (retired) 🎟️🎟️         a retired guide (no pale red square exists; closest)
    ⬜⬜ design spike · Reading the diff          a WATCHED session: not managed, only watched
    🟧🟧 (g) billing lead · Waiting on CI         a MANAGED (guided) session

A retired guide (one that handed over to a new guide) gets RETIRED_TITLE instead, on its next prompt and from then on
(override: SESSION_GUIDE_RETIRED_TITLE). Its marker holds `retired`, so the hook can't turn it red again.

A guided worker (marker `guided`) keeps its own title with GUIDED_PREFIX in front (override:
SESSION_GUIDE_GUIDED_PREFIX), so the user can tell at a glance which sessions don't need them. The hook prefixes the
title the session has now and prints nothing once it is prefixed. Repeated prefixes collapse to one, and a title
still carrying the bare "(g) " of older versions is upgraded. A watched session (marker `watched`) gets WATCHED_PREFIX
the same way (override: SESSION_GUIDE_WATCHED_PREFIX); `guided` and `watched` swap one prefix for the other. `unguided`
(marker `unguided`) takes either prefix off on the next prompt, after which the hook drops the marker. A guide or a
retired guide is never prefixed: `guided` and `watched` refuse them, and `mark` replaces a guided or watched marker.

A closed session (marker `done`, from `done <id>`: the guide closed a finished or obsolete worker) gets DONE_PREFIX in
place of the guided prefix (override: SESSION_GUIDE_DONE_PREFIX), the same way. `guided`, `watched` and `mark` refuse
it, so it is never orange, gray or red again; `done` refuses a guide or a retired guide (retire a guide instead).
The session-titles plugin answers the same hook events later and its title wins, so the prefix also goes into its
stored origin ($CLAUDE_CONFIG_DIR/session-titles/<session id>.json), whenever a marker is written and on every prompt:
then both hooks give the same title. Guides and retired guides get its `off` flag instead. No state file, no change.

--session (and the <id> of retire / guided / watched / unguided) defaults to $CLAUDE_CODE_SESSION_ID and may be an id
prefix.
Python 3 stdlib only.
"""
import argparse
import glob
import json
import os
import re
import sys

TITLE = ("\U0001f7e5\U0001f7e5 Sessions Manager ({managed} managed \u00b7 {watched} watched \u00b7 {new} new)"
         " \U0001f7e5\U0001f7e5")
RETIRED_TITLE = ("\U0001f39f\ufe0f\U0001f39f\ufe0f Sessions Manager (retired)"
                 " \U0001f39f\ufe0f\U0001f39f\ufe0f")
GUIDED_PREFIX = "\U0001f7e7\U0001f7e7 (g) "
WATCHED_PREFIX = "\u2b1c\u2b1c "
DONE_PREFIX = "\u2705 "
RETIRED = "retired"  # marker content for a retired guide, in place of a ledger path
GUIDED, UNGUIDED = "guided", "unguided"  # marker content for a MANAGED worker, and for one that just left
WATCHED = "watched"  # marker content for a WATCHED session
DONE = "done"  # marker content for a session the guide closed


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
    """{managed, watched, new, active} from the ledger, or None when it has no ## Sessions table.

    managed / watched count the Sessions table's rows by Level; new is the header's `New: <n>` line, the guide's count
    of untracked sessions active in the last 12 hours.
    """
    managed = watched = new = 0
    in_header, in_sessions, seen = True, False, False
    for line in open(ledger, errors="replace"):
        if line.startswith("## "):
            in_header, in_sessions = False, line.strip() == "## Sessions"
            continue
        found = re.match(r"New:\s*(\d+)", line) if in_header else None
        if found:
            new = int(found.group(1))
        if not in_sessions or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        seen = True
        level = cells[1].split()[0] if cells[1] else ""
        managed += level == "MANAGED"
        watched += level == "WATCHED"
    return dict(managed=managed, watched=watched, new=new, active=managed + watched) if seen else None


def marker_content(session_id):
    path = marker(session_id)
    return open(path).read().strip() if os.path.isfile(path) else None


def guided_prefix():
    return os.environ.get("SESSION_GUIDE_GUIDED_PREFIX") or GUIDED_PREFIX


def watched_prefix():
    return os.environ.get("SESSION_GUIDE_WATCHED_PREFIX") or WATCHED_PREFIX


def done_prefix():
    return os.environ.get("SESSION_GUIDE_DONE_PREFIX") or DONE_PREFIX


def worker_title(content, current):
    """The guided / watched / unguided / done title for `current`, or None when it is already right (or there is none
    yet)."""
    marks = [guided_prefix().strip(), watched_prefix().strip(), GUIDED_PREFIX.strip(), WATCHED_PREFIX.strip(),
             "\U0001f7e7\U0001f7e7", "(g)"] + [done_prefix().strip()] * (content == DONE)
    bare = current
    while any(m and bare.startswith(m) for m in marks):
        mark = next(m for m in marks if m and bare.startswith(m))
        bare = bare[len(mark):].lstrip()
    want = {GUIDED: guided_prefix() + bare, WATCHED: watched_prefix() + bare,
            DONE: done_prefix() + bare}.get(content, bare)
    return want if bare and want != current else None


def title_for(session_id, current=""):
    content = marker_content(session_id)
    if content is None:
        return None
    if content in (GUIDED, WATCHED, UNGUIDED, DONE):
        return worker_title(content, current)
    if content == RETIRED:
        return os.environ.get("SESSION_GUIDE_RETIRED_TITLE") or RETIRED_TITLE
    ledger = os.path.expanduser(content)
    found = counts(ledger)
    if found is None:
        return None
    return (os.environ.get("SESSION_GUIDE_TITLE") or TITLE).format(**found)


def cmd_hook():
    try:
        event = json.load(sys.stdin)
        sid = event["session_id"]
        current = (event.get("session_title") or "").strip()
        if marker_content(sid):
            sync_session_titles(sid, marker_content(sid))
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
    if marker_content(sid) in (RETIRED, DONE):
        raise SystemExit("%s is %s; a new guide needs a fresh session"
                         % (sid[:8], "a retired guide" if marker_content(sid) == RETIRED else "closed"))
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
    if content == DONE:
        raise SystemExit("%s is closed; a closed session is never managed again" % sid[:8])
    if content not in (None, GUIDED, WATCHED, UNGUIDED):
        raise SystemExit("%s is a guide%s; guides get no prefix" % (sid[:8], " (retired)" * (content == RETIRED)))
    write_marker(sid, GUIDED)
    print("%s is guided; %r goes before its title from its next prompt" % (sid[:8], guided_prefix()))
    return 0


def cmd_watched(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content == DONE:
        raise SystemExit("%s is closed; a closed session is never watched again" % sid[:8])
    if content not in (None, GUIDED, WATCHED, UNGUIDED):
        raise SystemExit("%s is a guide%s; guides get no prefix" % (sid[:8], " (retired)" * (content == RETIRED)))
    write_marker(sid, WATCHED)
    print("%s is watched; %r goes before its title from its next prompt" % (sid[:8], watched_prefix()))
    return 0


def cmd_unguided(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content not in (None, GUIDED, WATCHED, UNGUIDED):
        print("%s is %s, not a guided or watched worker; left as it is"
              % (sid[:8], "closed" if content == DONE else "a guide"))
        return 0
    write_marker(sid, UNGUIDED)
    print("%s is unmanaged; the prefix comes off its title on its next prompt" % sid[:8])
    return 0


def cmd_done(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content not in (None, GUIDED, WATCHED, UNGUIDED, DONE):
        raise SystemExit("%s is a %sguide; retire it instead" % (sid[:8], "retired " * (content == RETIRED)))
    write_marker(sid, DONE)
    print("%s is closed; %r goes before its title from its next prompt" % (sid[:8], done_prefix()))
    return 0


def write_marker(session_id, content):
    os.makedirs(os.path.dirname(marker(session_id)), exist_ok=True)
    with open(marker(session_id), "w") as f:
        f.write(content + "\n")
    sync_session_titles(session_id, content)


def sync_session_titles(session_id, content):
    """Make session-titles give the title we want, since its hook's answer overrides ours. Best effort."""
    home = os.path.join(config_dir(), "session-titles")
    path = os.path.join(home, session_id + ".json")
    if not os.path.isfile(path):
        return
    try:
        import fcntl  # not on Windows: the except below skips the sync there
        os.makedirs(os.path.join(home, "locks"), exist_ok=True)
        with open(os.path.join(home, "locks", session_id + ".lock"), "w") as lock:  # the one session-titles takes
            fcntl.flock(lock, fcntl.LOCK_EX)
            with open(path) as f:
                state = json.load(f)
            before = json.dumps(state)
            if content in (GUIDED, WATCHED, UNGUIDED, DONE):
                state["origin"] = worker_title(content, state.get("origin") or "") or state.get("origin") or ""
                last_set = worker_title(content, state.get("last_set") or "")
                if last_set:  # a resume restores last_set; keep the old one known, so it isn't read as a rename
                    state["history"] = (state.get("history") or []) + [last_set]
                    state["last_set"] = last_set
            else:
                state["off"] = True
            if json.dumps(state) != before:
                with open(path + ".tmp", "w") as f:
                    json.dump(state, f, ensure_ascii=False, indent=1)
                os.replace(path + ".tmp", path)
    except Exception:  # fail open, like the hook: a title is never worth an error
        pass


def main(argv=None):
    p = argparse.ArgumentParser(description="Pin the guide session's title and mark guided workers.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook", help="run as a UserPromptSubmit / SessionStart hook")
    mark = sub.add_parser("mark", help="mark a session as the guide of a ledger")
    mark.add_argument("ledger")
    mark.add_argument("--session")
    unmark = sub.add_parser("unmark", help="unmark a guide session")
    unmark.add_argument("--session")
    retire = sub.add_parser("retire", help="retire a guide that handed over (faded red title)")
    retire.add_argument("session", nargs="?")
    guided = sub.add_parser("guided", help='a MANAGED worker: orange blocks and "(g) " before its title')
    guided.add_argument("session", nargs="?")
    watched = sub.add_parser("watched", help="a WATCHED session: light gray blocks before its title")
    watched.add_argument("session", nargs="?")
    unguided = sub.add_parser("unguided", help="no longer managed or watched: the prefix comes off")
    unguided.add_argument("session", nargs="?")
    unwatched = sub.add_parser("unwatched", help="the same as unguided")
    unwatched.add_argument("session", nargs="?")
    done = sub.add_parser("done", help='closed: "\u2705 " before its title, never orange, gray or red again')
    done.add_argument("session", nargs="?")
    args = p.parse_args(argv)
    commands = {"hook": lambda a: cmd_hook(), "mark": cmd_mark, "unmark": cmd_unmark, "retire": cmd_retire,
                "guided": cmd_guided, "watched": cmd_watched, "unguided": cmd_unguided, "unwatched": cmd_unguided,
                "done": cmd_done}
    return commands[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
