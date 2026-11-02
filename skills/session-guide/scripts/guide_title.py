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
    python3 guide_title.py settle [<ledger>] [--idle-hours 2]  which sessions aren't settled, which reminders are due
    python3 guide_title.py waiting <id> "<what the user does>" it waits on the user: a reminder, due now
    python3 guide_title.py sleep <id> <hours>                  put that reminder off
    python3 guide_title.py unwait <id>                         it no longer waits on the user: the reminder goes
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

Every MANAGED or WATCHED session has to settle: either it waits on the user (a row in the ledger's `## Waiting on ...`
table, whose Remind at says when to ask again; `sleep` moves it) or it is closed (`done`, which also removes that row).
settle lists the sessions quiet for --idle-hours that are neither, and the reminders that are due; the hook gives a guide
both on every prompt. A running session, and one whose reminder sleeps, is left alone.

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
IDLE_HOURS = 2  # a MANAGED or WATCHED session quiet this long has to settle
SLEEP_HOURS = (1, 2, 8, 12, 24, 48)  # the periods the guide offers; `sleep` takes any positive number
TIME_FORMAT = "%Y-%m-%d %H:%M"  # Asked and Remind at: local time
WAITING_TABLE = ["| Session [id6] | What the user needs to do | Asked | Remind at |\n", "|---|---|---|---|\n"]


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


def row_id(cell):
    """The id6 (or longer) in a Sessions row's first cell, as `[3fa9c1]`: its first 6 characters, or None."""
    ids = re.findall(r"\[([0-9a-fA-F]{6,36})\]", cell)
    return ids[-1][:6].lower() if ids else None


def closed_ids():
    """The first 6 characters of every session whose marker says `done`."""
    found = set()
    for path in glob.glob(os.path.join(config_dir(), "session-guide", "guides", "*")):
        try:
            if open(path).read().strip() == DONE:
                found.add(os.path.basename(path)[:6].lower())
        except OSError:
            pass
    return found


def counts(ledger, session_id=""):
    """{managed, watched, active, new, tracked} from the ledger, or None when it has no ## Sessions table.

    managed / watched / active count the Sessions table's rows by Level; new is the live count from untracked();
    tracked is managed + watched. A row whose session is closed (marker `done`) doesn't count, and a session named by
    several rows counts once, at the topmost row's Level. A row with no [id] always counts.
    """
    managed = watched = active = 0
    in_sessions, seen = False, False
    closed, named = closed_ids(), set()
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
        rid = row_id(cells[0])
        if rid and (rid in closed or rid in named):
            continue
        named.add(rid)
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
    """What a guide should hear on this prompt: the sessions it hasn't asked about, the ones whose rows are DONE but
    are still marked, and the closed ones a running process keeps at their old title. None when there are none.

    Closed sessions whose process has ended are renamed here too, so a guide's prompts finish what `done` couldn't."""
    content = marker_content(session_id)
    if not content or content in WORKER_MARKERS + (RETIRED, DONE):
        return None
    ledger = os.path.expanduser(content)
    found, shut, held = untracked(ledger, session_id), closable(ledger), settle_closed()
    settling = settle_status(ledger, session_id)
    parts = []
    if held:
        parts.append("session-guide sweep: %d closed session(s) still have a running process, so their titles stay "
                     "orange until a prompt reaches them. SendMessage each the CLOSE message: %s"
                     % (len(held), ", ".join(s[:8] for s in held)))
    if found:
        lines = ["- " + describe(s) for s in found[:8]] + ["- and %d more" % (len(found) - 8)] * (len(found) > 8)
        parts.append("session-guide sweep: %d session(s) active in the last 12 h have no row in the ledger's Sessions "
                     "table:\n%s\n"
                     "Run `python3 %s active <id>` on each, then ask about them in this turn with AskUserQuestion (Manage / "
                     "Watch / Leave active / Ignore), and give each a row at the level the user picks."
                     % (len(found), "\n".join(lines), os.path.abspath(__file__)))
    if shut:
        parts.append("session-guide sweep: %d session(s) have only DONE rows in the ledger but are still marked, so "
                     "their titles stay orange. Run `python3 %s done <id>` on each: %s"
                     % (len(shut), os.path.abspath(__file__), ", ".join(s[:8] for s in shut)))
    if settling["unsettled"]:
        rows = settling["unsettled"]
        lines = ["- " + describe_unsettled(s) for s in rows[:8]] + ["- and %d more" % (len(rows) - 8)] * (len(rows) > 8)
        parts.append("session-guide settle: %d session(s) have gone quiet and aren't settled:\n%s\n"
                     "Peek each. Finished, nothing left on it or its subject: close it (`python3 %s done <id>`; ask the "
                     "user first if it is WATCHED or you aren't sure). Still needs the user: `python3 %s waiting <id> "
                     "\"<exact action, full link or command>\"`. More work for it: send it the next step."
                     % (len(rows), "\n".join(lines), os.path.abspath(__file__), os.path.abspath(__file__)))
    if settling["due"]:
        rows = settling["due"]
        lines = ["- %s: %s (asked %s)" % (r["session"], r["what"], r["asked"]) for r in rows[:8]]
        lines += ["- and %d more" % (len(rows) - 8)] * (len(rows) > 8)
        parts.append("session-guide settle: %d reminder(s) due:\n%s\n"
                     "Check each still applies (peek, PR state), then ask with AskUserQuestion, one question each, "
                     "repeating the full action: Done it / Nothing more to do: close it / Sleep 1, 2 or 8 hours / Sleep 12, "
                     "24 or 48 hours. A sleep answer gets an immediate second question for the exact period, then `python3 "
                     "%s sleep <id> <hours>`. Afterwards keep a wake scheduled for the next reminder that `settle` prints: "
                     "over 60 minutes away, a one-shot CronCreate rather than chained wakeups."
                     % (len(rows), "\n".join(lines), os.path.abspath(__file__)))
    return "\n".join(parts) or None


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


def closable(ledger):
    """[(id, title)] of sessions still marked managed / watched / active whose every row in the ledger is DONE: the
    guide closed them in the ledger but never ran `done`. Their job state alone says nothing: a worker's state turns
    done at every final message and the guide can resume it, so only a DONE row counts."""
    levels, in_sessions = {}, False
    for line in open(ledger, errors="replace"):
        if line.startswith("## "):
            in_sessions = line.strip() == "## Sessions"
        elif in_sessions and line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rid = row_id(cells[0]) if len(cells) > 1 else None
            if rid:
                levels.setdefault(rid, []).append(cells[1].split()[0] if cells[1] else "")
    found = []
    for path in glob.glob(os.path.join(config_dir(), "session-guide", "guides", "*")):
        sid = os.path.basename(path)
        if marker_content(sid) in (GUIDED, WATCHED, ACTIVE) and levels.get(sid[:6].lower()) and \
                all(level == "DONE" for level in levels[sid[:6].lower()]):
            found.append(sid)
    return sorted(found)


def split_row(line):
    """The cells of a table row. `\\|` is a pipe inside a cell: reminders hold shell commands."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip()[1:-1])]


def session_levels(ledger):
    """{id6: (level, first cell)} from the ## Sessions table; a session on several rows takes its topmost row's Level."""
    found, in_sessions = {}, False
    for line in open(ledger, errors="replace"):
        if line.startswith("## "):
            in_sessions = line.strip() == "## Sessions"
        elif in_sessions and line.lstrip().startswith("|"):
            cells = split_row(line)
            rid = row_id(cells[0]) if len(cells) > 1 else None
            ids = re.findall(r"\[([0-9a-fA-F]{6,36})\]", cells[0])
            if len(ids) > 1:  # a title can quote other refs, say "[065020] (ListAgents [fa18dd])": take the real session
                rid = next((i[:6].lower() for i in reversed(ids) if last_write(i[:6].lower())), rid)
            if rid:
                found.setdefault(rid, (re.match(r"[A-Za-z]*", cells[1]).group(), cells[0]))
    return found


def waiting_rows(ledger):
    """{id6: {session, what, asked, remind}} from the table in the ledger's `## Waiting on ...` section."""
    found, inside = {}, False
    for line in open(ledger, errors="replace"):
        if line.startswith("## "):
            inside = line.startswith("## Waiting on")
        elif inside and line.lstrip().startswith("|"):
            cells = split_row(line)
            rid = row_id(cells[0])
            if rid and len(cells) >= 4:
                found[rid] = dict(session=cells[0], what=cells[1].replace("\\|", "|"), asked=cells[2], remind=cells[3])
    return found


def write_waiting(ledger, rid, row):
    """Set session `rid`'s row in the waiting table to `row` (its 4 cells), or remove it when `row` is None. True when
    the ledger changed. Adds the section and the table when they are missing, and leaves any bullets there alone."""
    lines = open(ledger, errors="replace").read().splitlines(True)
    text = row and "| %s |\n" % " | ".join(c.replace("\n", " ").replace("|", "\\|") for c in row)
    start = next((i for i, l in enumerate(lines) if l.startswith("## Waiting on")), None)
    if start is None:
        if row is None:
            return False
        at = next((i for i, l in enumerate(lines) if l.startswith("## Open items")), len(lines))
        lines[at:at] = ["## Waiting on the user\n", "\n"]
        start = at
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    table = [i for i in range(start + 1, end) if lines[i].lstrip().startswith("|")]
    mine = [i for i in table if row_id(split_row(lines[i])[0]) == rid]
    if mine:
        lines[mine[0]:mine[0] + 1] = [text] if row else []
    elif row is None:
        return False
    elif table:
        lines.insert(table[-1] + 1, text)
    else:
        blank = [] if lines[start + 1:start + 2] == ["\n"] and end == start + 2 else ["\n"]
        lines[start + 1:start + 1] = WAITING_TABLE + [text] + blank
    with open(ledger + ".tmp", "w") as f:
        f.write("".join(lines))
    os.replace(ledger + ".tmp", ledger)
    return True


def last_write(rid):
    """(full session id, seconds since its transcript last changed), or None when it has no transcript any more."""
    paths = glob.glob(os.path.join(config_dir(), "projects", "*", rid + "*.jsonl"))
    if not paths:
        return None
    path = max(paths, key=os.path.getmtime)
    return os.path.basename(path)[:-6], time.time() - os.path.getmtime(path)


def job_state(session_id):
    try:
        with open(os.path.join(config_dir(), "jobs", session_id[:8], "state.json")) as f:
            return json.load(f).get("state") or ""
    except (OSError, ValueError):
        return ""


def settle_status(ledger, session_id="", idle_hours=IDLE_HOURS):
    """What is left to settle: {unsettled, due, asleep}.

    unsettled: MANAGED and WATCHED sessions, quiet for idle_hours and not running, with no waiting row and not closed.
    due / asleep: waiting rows of open sessions, by Remind at. A row whose time can't be read is due: never forgotten."""
    levels, rows, closed = session_levels(ledger), waiting_rows(ledger), closed_ids()
    unsettled, due, asleep = [], [], []
    for rid, (level, cell) in levels.items():
        if level not in ("MANAGED", "WATCHED") or rid in closed or rid in rows or rid == session_id[:6].lower():
            continue
        seen = last_write(rid)
        if seen is None:
            unsettled.append(dict(id=rid, session=cell, level=level, idle=None, state=""))
            continue
        sid, idle = seen
        content, state = marker_content(sid), job_state(sid)
        if content is not None and content not in WORKER_MARKERS:  # a guide: guides settle by handing over
            continue
        if idle >= idle_hours * 3600 and not (state == "working" and session_alive(sid)):
            unsettled.append(dict(id=rid, session=cell, level=level, idle=idle, state=state))
    for rid, row in rows.items():
        if rid in closed or levels.get(rid, ("", ""))[0] not in ("MANAGED", "WATCHED", "ACTIVE"):
            continue
        try:
            at = time.mktime(time.strptime(row["remind"], TIME_FORMAT))
        except ValueError:
            at = 0
        (due if at <= time.time() else asleep).append(dict(row, id=rid, at=at))
    return dict(unsettled=unsettled, due=sorted(due, key=lambda r: r["at"]), asleep=sorted(asleep, key=lambda r: r["at"]))


def describe_unsettled(row):
    if row["idle"] is None:
        return "%s, %s: its transcript is gone, so set its row's Level to DONE by hand" % (row["session"], row["level"])
    return "%s, %s: quiet %.0f h%s" % (row["session"], row["level"], row["idle"] / 3600,
                                       ", job state " + row["state"] if row["state"] else "")


def require_ledger():
    ledger = guide_ledger()
    if ledger is None:
        raise SystemExit("no single guide ledger found: run this from the guide")
    return ledger


def cmd_settle(args):
    ledger = os.path.expanduser(args.ledger or require_ledger())
    found = settle_status(ledger, os.environ.get("CLAUDE_CODE_SESSION_ID", ""), args.idle_hours)
    for row in found["unsettled"]:
        print("Unsettled: " + describe_unsettled(row))
    for row in found["due"]:
        print("Due: %s: %s (asked %s)" % (row["session"], row["what"], row["asked"]))
    for row in found["asleep"]:
        print("Asleep until %s: %s: %s" % (row["remind"], row["session"], row["what"]))
    print("%d unsettled, %d due, %d asleep" % (len(found["unsettled"]), len(found["due"]), len(found["asleep"])))
    if found["asleep"]:
        print("Next reminder: " + found["asleep"][0]["remind"])
    return 0


def cmd_waiting(args):
    sid, ledger = resolve_session(args.session), require_ledger()
    what = " ".join(args.what.split())
    if not what:
        raise SystemExit("say what the user needs to do")
    level, cell = session_levels(ledger).get(sid[:6].lower(), ("", ""))
    if level not in ("MANAGED", "WATCHED", "ACTIVE") or marker_content(sid) == DONE:
        raise SystemExit("%s has no open row in ## Sessions (level %r); give it one first" % (sid[:8], level))
    now = time.strftime(TIME_FORMAT)
    old = waiting_rows(ledger).get(sid[:6].lower())
    write_waiting(ledger, sid[:6].lower(), [cell, what, old["asked"] if old else now, old["remind"] if old else now])
    print("%s waits on the user; reminder at %s" % (sid[:8], old["remind"] if old else now))
    return 0


def cmd_sleep(args):
    sid, ledger = resolve_session(args.session), require_ledger()
    if args.hours <= 0:
        raise SystemExit("sleep for a positive number of hours; the guide offers %s" % ", ".join(map(str, SLEEP_HOURS)))
    row = waiting_rows(ledger).get(sid[:6].lower())
    if not row:
        raise SystemExit("%s has no reminder; run `waiting` first" % sid[:8])
    remind = time.strftime(TIME_FORMAT, time.localtime(time.time() + args.hours * 3600))
    write_waiting(ledger, sid[:6].lower(), [row["session"], row["what"], row["asked"], remind])
    print("%s sleeps until %s" % (sid[:8], remind))
    asleep = settle_status(ledger)["asleep"]
    if asleep:
        print("Next reminder: " + asleep[0]["remind"])
    return 0


def cmd_unwait(args):
    sid, ledger = resolve_session(args.session), require_ledger()
    gone = write_waiting(ledger, sid[:6].lower(), None)
    print("%s %s" % (sid[:8], "no longer waits on the user" if gone else "had no reminder"))
    return 0


def cmd_sweep(args):
    ledger = args.ledger or marker_content(resolve_session(None))
    if not ledger or not os.path.isfile(os.path.expanduser(ledger)):
        raise SystemExit("no ledger: pass its path, or run this from the guide")
    found = untracked(os.path.expanduser(ledger), os.environ.get("CLAUDE_CODE_SESSION_ID", ""), args.hours)
    for session in found:
        print(describe(session))
    print("New: %d" % len(found))
    for sid in closable(os.path.expanduser(ledger)):
        print("Closable: [%s] has only DONE rows but is still marked; run `done %s`" % (sid[:8], sid))
    for sid in settle_closed():
        print("Held: [%s] is closed but a process still holds it; SendMessage it the CLOSE message" % sid[:8])
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


def guide_ledger():
    """The ledger in this session's guide marker, else the one ledger all guide markers name, else None."""
    own = marker(os.environ.get("CLAUDE_CODE_SESSION_ID") or "-")
    found = set()
    for path in [own] + glob.glob(os.path.join(config_dir(), "session-guide", "guides", "*")):
        content = open(path).read().strip() if os.path.isfile(path) else ""
        if content and content not in WORKER_MARKERS + (RETIRED, DONE) and os.path.isfile(os.path.expanduser(content)):
            if path == own:
                return os.path.expanduser(content)
            found.add(os.path.expanduser(content))
    return found.pop() if len(found) == 1 else None


def close_rows(ledger, session_id):
    """Set the Level of every Sessions row naming `session_id` to DONE; how many rows changed."""
    want, changed, in_sessions, out = session_id[:6].lower(), 0, False, []
    for line in open(ledger, errors="replace").read().splitlines(True):
        if line.startswith("## "):
            in_sessions = line.strip() == "## Sessions"
        elif in_sessions and line.lstrip().startswith("|"):
            parts = line.split("|")
            if len(parts) > 3 and row_id(parts[1]) == want and parts[2].split()[:1] not in ([], ["DONE"]):
                parts[2] = re.sub(r"\S+", "DONE", parts[2], count=1)
                line, changed = "|".join(parts), changed + 1
        out.append(line)
    if changed:
        with open(ledger + ".tmp", "w") as f:
            f.write("".join(out))
        os.replace(ledger + ".tmp", ledger)
    return changed


def session_alive(session_id):
    """True when a running Claude process holds this session (~/.claude/sessions/<pid>.json with a live pid)."""
    for path in glob.glob(os.path.join(config_dir(), "sessions", "*.json")):
        try:
            info = json.load(open(path))
            if info.get("sessionId") == session_id:
                os.kill(int(info["pid"]), 0)
                return True
        except PermissionError:
            return True  # the process exists, it is just not ours
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return False


def retitle_stopped_job(session_id):
    """Put the closed title into the job's state.json `name`, which is what `claude agents` and claude-top show, when
    no process holds the session. Returns a line to print, or None when there is nothing to do.

    Claude Code has no command that renames a session without running a turn in it (the hook answer and /rename both
    need a live session), so for a session that is already over this one-key edit is the only way. A live session is
    never touched: its own process owns the file, and its next prompt applies the hook's title."""
    path = os.path.join(config_dir(), "jobs", session_id[:8], "state.json")
    try:
        with open(path) as f:
            state = json.load(f)
        if state.get("sessionId") != session_id or not state.get("name"):
            return None
        if session_alive(session_id):
            return ("its process is still running: its title changes on its next prompt (send it CLOSE), or at a guide's "
                    "next prompt after the process ends")
        name = worker_title(DONE, state["name"])
        if not name:
            return None
        state["name"] = name
        with open(path + ".tmp", "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(path + ".tmp", path)
        return "no process holds it, so its job name was set to %r (an edit of state.json's name; no command renames a finished session)" % name
    except (OSError, ValueError):
        return None


def settle_closed():
    """Finish `done` for every closed session whose job still has its old name: rename it if its process has ended.

    `done` can't rename a session a process still holds, and a closed session never gets another prompt on its own, so
    the rename has to be retried. Returns the ids a running process holds at a colored title; only a prompt can change
    those. One with a plain title isn't returned, since a check mark isn't worth a turn: it is renamed when it ends."""
    held = []
    for path in glob.glob(os.path.join(config_dir(), "session-guide", "guides", "*")):
        sid = os.path.basename(path)
        if marker_content(sid) != DONE:
            continue
        try:
            with open(os.path.join(config_dir(), "jobs", sid[:8], "state.json")) as f:
                state = json.load(f)
        except (OSError, ValueError):
            continue
        if state.get("sessionId") != sid or not worker_title(DONE, state.get("name") or ""):
            continue
        if not session_alive(sid):
            retitle_stopped_job(sid)
        elif worker_title(UNGUIDED, state["name"]):  # it has a prefix to take off
            held.append(sid)
    return sorted(held)


def cmd_done(args):
    sid = resolve_session(args.session)
    content = marker_content(sid)
    if content is not None and content not in WORKER_MARKERS + (DONE,):
        raise SystemExit("%s is a %sguide; retire it instead" % (sid[:8], "retired " * (content == RETIRED)))
    write_marker(sid, DONE)
    print("%s is closed; %r goes before its title" % (sid[:8], done_prefix()))
    note = retitle_stopped_job(sid)
    print(note or "its title changes on its next prompt")
    ledger = guide_ledger()
    if ledger is None:
        print("no single guide ledger found: set its row's Level to DONE yourself")
    else:
        print("%d row(s) in %s set to DONE" % (close_rows(ledger, sid), ledger))
        write_waiting(ledger, sid[:6].lower(), None)
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
    settle = sub.add_parser("settle", help="list sessions that aren't settled and reminders that are due")
    settle.add_argument("ledger", nargs="?")
    settle.add_argument("--idle-hours", type=float, default=IDLE_HOURS)
    waiting = sub.add_parser("waiting", help="this session waits on the user: a reminder, due now")
    waiting.add_argument("session")
    waiting.add_argument("what")
    sleep = sub.add_parser("sleep", help="put a session's reminder off")
    sleep.add_argument("session")
    sleep.add_argument("hours", type=float)
    unwait = sub.add_parser("unwait", help="it no longer waits on the user: the reminder goes")
    unwait.add_argument("session")
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
                "unguided": cmd_unguided, "unwatched": cmd_unguided, "done": cmd_done, "sweep": cmd_sweep,
                "settle": cmd_settle, "waiting": cmd_waiting, "sleep": cmd_sleep, "unwait": cmd_unwait}
    return commands[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
