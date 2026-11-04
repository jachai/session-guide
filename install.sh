#!/bin/sh
# Install session-guide as a plain Claude Code or Codex skill.
#   ./install.sh                      copy to ~/.claude/skills/session-guide
#   ./install.sh --codex              copy to ~/.codex/skills/session-guide
#   ./install.sh --codex --link       symlink the Codex skill (for working on this repo)
#   ./install.sh --codex --uninstall  remove only the skill; keep ledgers
set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME=claude
ACTION=copy
for arg in "$@"; do
  case "$arg" in
    --codex) RUNTIME=codex ;;
    --claude) RUNTIME=claude ;;
    --link) ACTION=link ;;
    --uninstall) ACTION=uninstall ;;
    *) echo "usage: $0 [--claude | --codex] [--link | --uninstall]" >&2; exit 2 ;;
  esac
done

if [ "$RUNTIME" = codex ]; then
  CONFIG="${CODEX_HOME:-$HOME/.codex}"
else
  CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
fi
DEST="$CONFIG/skills/session-guide"

case "$ACTION" in
  uninstall)
    rm -rf "$DEST"
    echo "removed the skill; ledgers and playbooks in $CONFIG/session-guide are kept"
    ;;
  link|copy)
    mkdir -p "$CONFIG/skills" "$CONFIG/session-guide/playbooks"
    rm -rf "$DEST"
    if [ "$ACTION" = link ]; then
      ln -s "$ROOT/skills/session-guide" "$DEST"
    else
      cp -R "$ROOT/skills/session-guide" "$DEST"
    fi
    echo "installed the skill at $DEST"
    if [ "$RUNTIME" = codex ]; then
      echo "in Codex: ask this thread to use session-guide as the guide for its multi-agent tree"
    else
      echo "in Claude Code: /session-guide makes a session the guide; /session-guide join opts a worker in"
      echo
      echo "to pin the guide's title, add these hooks to $CONFIG/settings.json (merge with any hooks you have):"
      sed "s#\$HOME/.claude/skills/session-guide#$DEST#" "$ROOT/examples/settings-snippet.json"
    fi
    ;;
esac
