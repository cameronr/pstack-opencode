#!/usr/bin/env bash
# Install pstack skills and agents into an opencode config directory.
#
#   ./install.sh              copy skills/ into $PREFIX/skills/, agents/ into $PREFIX/agents/
#   ./install.sh --link       symlink instead of copy (repo edits show up immediately)
#   ./install.sh --prefix DIR install into DIR instead of $HOME/.config/opencode
#   ./install.sh -y           skip the confirmation prompt (for scripting)
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--link] [--prefix DIR] [-y|--yes] [-h|--help]

Install pstack into an opencode config directory.

  --link        Symlink each skill and agent into place instead of copying.
                Re-runs and repo edits are picked up without reinstalling.
  --prefix DIR  Target config directory (default: $HOME/.config/opencode).
  -y, --yes     Skip the confirmation prompt (for scripting).
  -h, --help    Show this help.

Skills are installed to $PREFIX/skills/, agents to $PREFIX/agents/.
Entries with the same name are replaced; entries that are not pstack's
are never touched. Re-runs prune items that no longer exist in the repo
(tracked via $PREFIX/.pstack-manifest). Safe to re-run.
EOF
}

MODE=copy
PREFIX="$HOME/.config/opencode"
ASSUME_YES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --link) MODE=link ;;
    --prefix)
      [ $# -ge 2 ] || { echo "error: --prefix needs a directory" >&2; exit 1; }
      PREFIX="$2"; shift ;;
    --prefix=*) PREFIX="${1#--prefix=}" ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

SKILLS_SRC="$REPO/skills"
AGENTS_SRC="$REPO/agents"
SKILLS_DST="$PREFIX/skills"
AGENTS_DST="$PREFIX/agents"
MANIFEST="$PREFIX/.pstack-manifest"

[ -d "$SKILLS_SRC" ] || { echo "error: $SKILLS_SRC not found" >&2; exit 1; }
[ -d "$AGENTS_SRC" ] || { echo "error: $AGENTS_SRC not found" >&2; exit 1; }

SKILLS=()
for d in "$SKILLS_SRC"/*/; do
  SKILLS+=("$(basename "${d%/}")")
done

AGENTS=()
for f in "$AGENTS_SRC"/*.md; do
  [ -e "$f" ] || continue
  AGENTS+=("$(basename "$f")")
done

# Prune candidates: manifest entries whose upstream source is gone.
PRUNED=()
if [ -f "$MANIFEST" ]; then
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    case "$entry" in
      skills/*)
        [ -e "$SKILLS_SRC/${entry#skills/}" ] || PRUNED+=("$entry") ;;
      agents/*)
        [ -e "$AGENTS_SRC/${entry#agents/}" ] || PRUNED+=("$entry") ;;
    esac
  done < "$MANIFEST"
fi

how="copy"
[ "$MODE" = link ] && how="link"

echo "Plan: install pstack via $how into $PREFIX"
echo "  skills: ${#SKILLS[@]} to install/refresh -> $SKILLS_DST/"
echo "  agents: ${#AGENTS[@]} to install/refresh -> $AGENTS_DST/"
for entry in ${PRUNED[@]+"${PRUNED[@]}"}; do
  echo "  prune: $entry (no longer upstream)"
done

if [ "$ASSUME_YES" -eq 0 ]; then
  printf 'Proceed? [y/N] '
  read -r answer || answer=""
  case "${answer:-}" in
    y|Y|yes|YES|Yes) ;;
    *) echo "Aborted. Nothing changed." >&2; exit 0 ;;
  esac
fi

# Remove manifest-listed items that no longer exist upstream.
for entry in ${PRUNED[@]+"${PRUNED[@]}"}; do
  rm -rf "$PREFIX/$entry"
  echo "pruned $entry (no longer upstream)"
done

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

for name in ${SKILLS[@]+"${SKILLS[@]}"}; do
  install_entry "$SKILLS_SRC/$name" "$SKILLS_DST/$name"
done

for name in ${AGENTS[@]+"${AGENTS[@]}"}; do
  install_entry "$AGENTS_SRC/$name" "$AGENTS_DST/$name"
done

# Rewrite the manifest: one installed item per line, sorted.
{
  for name in ${SKILLS[@]+"${SKILLS[@]}"}; do
    printf 'skills/%s\n' "$name"
  done
  for name in ${AGENTS[@]+"${AGENTS[@]}"}; do
    printf 'agents/%s\n' "$name"
  done
} | sort > "$MANIFEST"

how="copied"
[ "$MODE" = link ] && how="symlinked"

cat <<EOF
pstack installed ($how):
  ${#SKILLS[@]} skills  -> $SKILLS_DST/
  ${#AGENTS[@]} agents  -> $AGENTS_DST/

Next steps:
  1. Restart opencode so it picks the new skills and agents up.
  2. Optional: run the setup-pstack skill (/setup-pstack) to configure
     per-role subagent types and, if you want, per-role models.
  3. On opencode2 you can skip this installer for skills and point your
     config at the repo instead:
       "skills": ["<path-to-this-repo>/skills"]
     The "skills" entry covers skills only. Agents still need this
     installer (or a manual copy of agents/*.md into the agents dir),
     so edits to the repo are picked up directly.
EOF
