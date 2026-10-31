#!/usr/bin/env python3
"""guide_title: keep the guide session's title pinned, with live counts from its ledger, and mark guided workers.

    python3 guide_title.py mark <ledger.md> [--session <id>]   this session is a guide
    python3 guide_title.py unmark [--session <id>]             it no longer is
    python3 guide_title.py retire [<id>]                       it handed over: faded red title, never red again
    python3 guide_title.py guided [<id>]                       a MANAGED worker: orange blocks + "(g) " first
    python3 guide_title.py watched [<id>]                      a WATCHED session: light gray blocks first
    python3 guide_title.py active [<id>]                       running, not managed or watched: blue blocks first
    python3 guide_title.py unguided [<id>]                     no longer managed or watched: the prefix comes off
    python3 guide_title.py unwatched [<id>]                    the same as unguided
    python3 guide_title.py done [<id>]                         closed: "✅ " before its title, never orange again
    python3 guide_title.py sweep [<ledger>] [--hours 12]       list recently active sessions the ledger doesn't have
    python3 guide_title.py hook                                UserPromptSubmit / SessionStart hook (JSON on stdin)

A marked session gets this title on every prompt and every start, so a rename (by hand or by another titling hook)
is undone on the next turn:

    🟥🟥 Sessions Manager (2 managed · 1 watched · 3 active · 1 new) 🟥🟥

managed, watched and active count those rows in the ledger's `## Sessions` table; new is the live count of sessions
active in the last 12 hours with no row there (see sweep). To pick your own format, set SESSION_GUIDE_TITLE (for
hooks: in settings.json "env") with {managed}, {watched}, {active}, {new} and {tracked} (managed + watched)
placeholders. Avoid `*`: some title tools strip markdown. Keep
the "🟥🟥 Sessions Manager" start if you use claude-top: it falls back to it for a session without a marker. The
marker is
$CLAUDE_CONFIG_DIR/session-guide/guides/<session id> (default ~/.claude), holding the ledger path. The hook fails
open: an unmarked session, a missing or unreadable ledger, or bad input prints nothing and exits 0.

Every title kind has its own color, so the agents view reads at a glance:

    🟥🟥 Sessions Manager (...) 🟥🟥              the active guide
    🎟️🎟️ Sessions Manager (retired) 🎟️🎟️         a retired guide (no pale red square exists; closest)
    ⬜⬜ design spike · Reading the diff          a WATCHED session: not managed, only watched
    🟦🟦 notes cleanup · Tidying the index        an ACTIVE session: running, not managed or watched
    🟧🟧 (g) billing lead · Waiting on CI         a MANAGED (guided) session

A retired guide (one that handed over to a new guide) gets RETIRED_TITLE instead, on its next prompt and from then on
(override: SESSION_GUIDE_RETIRED_TITLE). Its marker holds `retired`, so the hook can't turn it red again.

A guided worker (marker `guided`) keeps its own title with GUIDED_PREFIX in front (override:
SESSION_GUIDE_GUIDED_PREFIX), so the user can tell at a glance which sessions don't need them. The hook prefixes the
title the session has now and prints nothing once it is prefixed. Repeated prefixes collapse to one, and a title
still carrying the bare "(g) " of older versions is upgraded. A watched session (marker `watched`) gets WATCHED_PREFIX
the same way (override: SESSION_GUIDE_WATCHED_PREFIX), and so does an active one (marker `active`, ACTIVE_PREFIX,
override: SESSION_GUIDE_ACTIVE_PREFIX); `guided`, `watched` and `active` swap one prefix for another. `unguided`
(marker `unguided`) takes any of them off on the next prompt, after which the hook drops the marker. A guide or a
retired guide is never prefixed: all three refuse them, and `mark` replaces their markers.

sweep lists sessions whose transcript changed in the window and that have no row in the ledger's `## Sessions` table,
leaving out this session, closed sessions, guides and `claude -p` runs. On every prompt the hook gives a guide that
list as additionalContext, until each session has a row, so a new session can't slip by unasked.

A closed session (marker `done`, from `done <id>`: the guide closed a finished or obsolete worker) gets DONE_PREFIX in
place of the guided prefix (override: SESSION_GUIDE_DONE_PREFIX), the same way. `guided`, `watched`, `active` and `mark`
refuse it, so it is never orange, gray, blue or red again; `done` refuses a guide or a retired guide (retire a guide instead).
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
import time

TITLE = ("\U0001f7e5\U0001f7e5 Sessions Manager ({managed} managed \u00b7 {watched} watched \u00b7 {active} active"
         " \u00b7 {new} new) \U0001f7e5\U0001f7e5")
RETIRED_TITLE = ("\U0001f39f\ufe0f\U0001f39f\ufe0f Sessions Manager (retired)"
                 " \U0001f39f\ufe0f\U0001f39f\ufe0f")
GUIDED_PREFIX = "\U0001f7e7\U0001f7e7 (g) "
WATCHED_PREFIX = "\u2b1c\u2b1c "
ACTIVE_PREFIX = "\U0001f7e6\U0001f7e6 "
DONE_PREFIX = "\u2705 "
RETIRED = "retired"  # marker content for a retired guide, in place of a ledger path
GUIDED, UNGUIDED = "guided", "unguided"  # marker content for a MANAGED worker, and for one that just left
WATCHED, ACTIVE = "watched", "active"  # marker content for a WATCHED session and for an ACTIVE one
WORKER_MARKERS = (GUIDED, WATCHED, ACTIVE, UNGUIDED)
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


def counts(ledger, session_id=""):
    """{managed, watched, active, new, tracked} from the ledger, or None when it has no ## Sessions table.

    managed / watched / active count the Sessions table's rows by Level; new is the live count from untracked();
    tracked is managed + watched.
    """
    managed = watched = active = 0
    in_sessions, seen = False, False
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
        active += level == "ACTIVE"
    if not seen:
        return None
    return dict(managed=managed, watched=watched, active=active, new=len(untracked(ledger, session_id)),
                tracked=managed + watched)


def transcript_facts(path):
    """(entrypoint, latest title) of a transcript, from its first lines and its last 256 KB."""
    entrypoint, title = "", ""
    with open(path, "rb") as f:
        for _ in range(40):
            found = re.search(rb'"entrypoint":\s*"([^"]+)"', f.readline())
            if found:
                entrypoint = found.group(1).decode(errors="replace")
                break
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 256 * 1024))
        for line in f.read().splitlines():
            if b'"customTitle"' in line:
                try:
                    title = json.loads(line).get("customTitle") or title
                except ValueError:  # the cut-off first line of the tail
                    pass
    return entrypoint, title


def untracked(ledger, session_id="", hours=12):
    """[{id, age, title}], newest first: recently active sessions with no row in the ledger's ## Sessions table."""
    known, in_sessions = set(), False
    for line in open(ledger, errors="replace"):
        if line.startswith("## "):
            in_sessions = line.strip() == "## Sessions"
        elif in_sessions:
            known.update(re.findall(r"\b[0-9a-f]{6,8}\b", line))
    now, found = time.time(), []
    for path in glob.glob(os.path.join(config_dir(), "projects", "*", "*.jsonl")):
        try:
            age = now - os.path.getmtime(path)
            sid = os.path.basename(path)[:-6]
            if (age > hours * 3600 or sid == session_id or not os.path.getsize(path)
                    or any(sid.startswith(k) for k in known)):
                continue
            content = marker_content(sid)
            if content is not None and content not in WORKER_MARKERS:  # closed, retired or a guide
                continue
            entrypoint, title = transcript_facts(path)
            if not entrypoint.startswith("sdk"):  # `claude -p` runs are scripts, not sessions to manage
                found.append(dict(id=sid, age=age, title=title))
        except OSError:  # a transcript removed while we read
            continue
    return sorted(found, key=lambda s: s["age"])


def describe(session):
    return "'%s' [%s], active %dm ago" % (session["title"] or "no title yet", session["id"][:8], session["age"] // 60)


def guide_context(session_id):
    """What a guide should hear on this prompt: the sessions it hasn't asked about. None when there are none."""
    content = marker_content(session_id)
    if not content or content in WORKER_MARKERS + (RETIRED, DONE):
        return None
    found = untracked(os.path.expanduser(content), session_id)
    if not found:
        return None
    lines = ["- " + describe(s) for s in found[:8]] + ["- and %d more" % (len(found) - 8)] * (len(found) > 8)
    return ("session-guide sweep: %d session(s) active in the last 12 h have no row in the ledger's Sessions table:"
            "\n%s\n"
            "Run `python3 %s active <id>` on each, then ask about them in this turn with AskUserQuestion (Manage / "
            "Watch / Leave active / Ignore), and give each a row at the level the user picks."
            % (len(found), "\n".join(lines), os.path.abspath(__file__)))


def marker_content(session_id):
    path = marker(session_id)
    return open(path).read().strip() if os.path.isfile(path) else None


def guided_prefix():
    return os.environ.get("SESSION_GUIDE_GUIDED_PREFIX") or GUIDED_PREFIX


def watched_prefix():
    return os.environ.get("SESSION_GUIDE_WATCHED_PREFIX") or WATCHED_PREFIX


def done_prefix():
    return os.environ.get("SESSION_GUIDE_DONE_PREFIX") or DONE_PREFIX


def active_prefix():
    return os.environ.get("SESSION_GUIDE_ACTIVE_PREFIX") or ACTIVE_PREFIX


def worker_title(content, current):
    """The guided / watched / active / unguided / done title for `current`, or None when it is already right (or there is none
    yet)."""
    marks = [guided_prefix().strip(), watched_prefix().strip(), active_prefix().strip(), GUIDED_PREFIX.strip(),
             WATCHED_PREFIX.strip(), ACTIVE_PREFIX.strip(), "\U0001f7e7\U0001f7e7", "(g)"] + [done_prefix().strip()] * (content == DONE)
    bare = current
    while any(m and bare.startswith(m) for m in marks):
        mark = next(m for m in marks if m and bare.startswith(m))
        bare = bare[len(mark):].lstrip()
    want = {GUIDED: guided_prefix() + bare, WATCHED: watched_prefix() + bare, ACTIVE: active_prefix() + bare,
            DONE: done_prefix() + bare}.get(content, bare)
    return want if bare and want != current else None


def title_for(session_id, current=""):
    content = marker_content(session_id)
    if content is None:
        return None
    if content in WORKER_MARKERS + (DONE,):
        return worker_title(content, current)
    if content == RETIRED:
        return os.environ.get("SESSION_GUIDE_RETIRED_TITLE") or RETIRED_TITLE
    ledger = os.path.expanduser(content)
    found = counts(ledger, session_id)
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
        output = {"hookEventName": event.get("hook_event_name", "UserPromptSubmit")}
        context = guide_context(sid)
        if title:
            output["sessionTitle"] = title
        if context:
            output["additionalContext"] = context
        if title or context:
            json.dump({"hookSpecificOutput": output}, sys.stdout)  # ASCII-escaped: any locale
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


def set_level(args, level, prefix):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content == DONE:
        raise SystemExit("%s is closed; a closed session gets no new level" % sid[:8])
    if content is not None and content not in WORKER_MARKERS:
        raise SystemExit("%s is a guide%s; guides get no prefix" % (sid[:8], " (retired)" * (content == RETIRED)))
    write_marker(sid, level)
    print("%s is %s; %r goes before its title from its next prompt" % (sid[:8], level, prefix))
    return 0


def cmd_sweep(args):
    ledger = args.ledger or marker_content(resolve_session(None))
    if not ledger or not os.path.isfile(os.path.expanduser(ledger)):
        raise SystemExit("no ledger: pass its path, or run this from the guide")
    found = untracked(os.path.expanduser(ledger), os.environ.get("CLAUDE_CODE_SESSION_ID", ""), args.hours)
    for session in found:
        print(describe(session))
    print("New: %d" % len(found))
    return 0


def cmd_unguided(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content is not None and content not in WORKER_MARKERS:
        print("%s is %s, not a guided or watched worker; left as it is"
              % (sid[:8], "closed" if content == DONE else "a guide"))
        return 0
    write_marker(sid, UNGUIDED)
    print("%s is unmanaged; the prefix comes off its title on its next prompt" % sid[:8])
    return 0


def cmd_done(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content is not None and content not in WORKER_MARKERS + (DONE,):
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
            if content in WORKER_MARKERS + (DONE,):
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
    active = sub.add_parser("active", help="running, not managed or watched: blue blocks before its title")
    active.add_argument("session", nargs="?")
    sweep = sub.add_parser("sweep", help="list recently active sessions the ledger has no row for")
    sweep.add_argument("ledger", nargs="?")
    sweep.add_argument("--hours", type=float, default=12)
    unguided = sub.add_parser("unguided", help="no longer managed or watched: the prefix comes off")
    unguided.add_argument("session", nargs="?")
    unwatched = sub.add_parser("unwatched", help="the same as unguided")
    unwatched.add_argument("session", nargs="?")
    done = sub.add_parser("done", help='closed: "\u2705 " before its title, never orange, gray, blue or red again')
    done.add_argument("session", nargs="?")
    args = p.parse_args(argv)
    commands = {"hook": lambda a: cmd_hook(), "mark": cmd_mark, "unmark": cmd_unmark, "retire": cmd_retire,
                "guided": lambda a: set_level(a, GUIDED, guided_prefix()),
                "watched": lambda a: set_level(a, WATCHED, watched_prefix()),
                "active": lambda a: set_level(a, ACTIVE, active_prefix()),
                "unguided": cmd_unguided, "unwatched": cmd_unguided, "done": cmd_done, "sweep": cmd_sweep}
    return commands[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
