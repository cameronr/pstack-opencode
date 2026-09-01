#!/usr/bin/env bash
# Install pstack skills and agents into an opencode config directory.
#
#   ./install.sh              copy skills/ into $PREFIX/skills/, agents/ into $PREFIX/agent/
#   ./install.sh --link       symlink instead of copy (repo edits show up immediately)
#   ./install.sh --prefix DIR install into DIR instead of $HOME/.config/opencode
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--link] [--prefix DIR] [-h|--help]

Install pstack into an opencode config directory.

  --link        Symlink each skill and agent into place instead of copying.
                Re-runs and repo edits are picked up without reinstalling.
  --prefix DIR  Target config directory (default: $HOME/.config/opencode).
  -h, --help    Show this help.

Skills are installed to $PREFIX/skills/, agents to $PREFIX/agent/.
Entries with the same name are replaced; entries that are not pstack's
are never touched. Safe to re-run.
EOF
}

MODE=copy
PREFIX="$HOME/.config/opencode"

while [ $# -gt 0 ]; do
  case "$1" in
    --link) MODE=link ;;
    --prefix)
      [ $# -ge 2 ] || { echo "error: --prefix needs a directory" >&2; exit 1; }
      PREFIX="$2"; shift ;;
    --prefix=*) PREFIX="${1#--prefix=}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

SKILLS_SRC="$REPO/skills"
AGENTS_SRC="$REPO/agents"
SKILLS_DST="$PREFIX/skills"
AGENTS_DST="$PREFIX/agent"

[ -d "$SKILLS_SRC" ] || { echo "error: $SKILLS_SRC not found" >&2; exit 1; }
[ -d "$AGENTS_SRC" ] || { echo "error: $AGENTS_SRC not found" >&2; exit 1; }

mkdir -p "$SKILLS_DST" "$AGENTS_DST"

install_entry() {
  # install_entry <src> <dst>
  # Replace whatever is at dst (old symlink, previously copied dir or file).
  # Only ever targets pstack's own names, so foreign entries are untouched.
  local src="$1" dst="$2"
  rm -rf "$dst"
  if [ "$MODE" = link ]; then
    ln -s "$src" "$dst"
  else
    cp -R "$src" "$dst"
  fi
}

skill_count=0
for d in "$SKILLS_SRC"/*/; do
  name=$(basename "$d")
  install_entry "${d%/}" "$SKILLS_DST/$name"
  skill_count=$((skill_count + 1))
done

agent_count=0
for f in "$AGENTS_SRC"/*.md; do
  [ -e "$f" ] || continue
  name=$(basename "$f")
  install_entry "$f" "$AGENTS_DST/$name"
  agent_count=$((agent_count + 1))
done

how="copied"
[ "$MODE" = link ] && how="symlinked"

cat <<EOF
pstack installed ($how):
  $skill_count skills  -> $SKILLS_DST/
  $agent_count agents  -> $AGENTS_DST/

Next steps:
  1. Restart opencode so it picks the new skills and agents up.
  2. Optional: run the setup-pstack skill (/setup-pstack) to configure
     per-role subagent types and, if you want, per-role models.
  3. On opencode2 you can skip this installer for skills and point your
     config at the repo instead:
       "skills": ["<path-to-this-repo>/skills"]
     The "skills" entry covers skills only. Agents still need this
     installer (or a manual copy of agents/*.md into the agent dir),
     so edits to the repo are picked up directly.
EOF
