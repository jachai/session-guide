#!/bin/sh
# Install session-guide as a plain Claude Code skill (no plugin system).
#   ./install.sh             copy the skill to ~/.claude/skills/session-guide
#   ./install.sh --link      symlink it instead (for working on this repo)
#   ./install.sh --uninstall remove the skill (your ledgers in ~/.claude/session-guide are kept)
set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
DEST="$CONFIG/skills/session-guide"

case "${1:-}" in
  --uninstall)
    rm -rf "$DEST"
    echo "removed the skill; ledgers and playbooks in $CONFIG/session-guide are kept"
    ;;
  --link|"")
    mkdir -p "$CONFIG/skills" "$CONFIG/session-guide/playbooks"
    rm -rf "$DEST"
    if [ "${1:-}" = "--link" ]; then
      ln -s "$ROOT/skills/session-guide" "$DEST"
    else
      cp -R "$ROOT/skills/session-guide" "$DEST"
    fi
    echo "installed the skill at $DEST"
    echo "in Claude Code: /session-guide makes a session the guide; /session-guide join opts a worker in"
    ;;
  *)
    echo "usage: $0 [--link | --uninstall]" >&2
    exit 2
    ;;
esac
