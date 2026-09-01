#!/usr/bin/env python3
"""Upstream drift check for the pstack opencode port.

Fetches upstream pstack/ (from the original backnotprop/pstack repo or a
local checkout), applies the port's mechanical convention mapping
(Cursor -> ZCode -> opencode, deterministic substitutions only), diffs the
mapped copy against this repo's skills/ and agents/, and reports what
upstream changed that we have not absorbed.

Files that carry one-off SEMANTIC port edits (transcript rewrites, agent
frontmatter, model wording) cannot be reproduced by the mapping; they are
listed in SEMANTIC below and flagged [SEMANTIC] in the report so a human
re-applies those edits when upstream touches them.

Usage:
    python3 scripts/check-upstream.py                    # default: github.com/backnotprop/pstack
    python3 scripts/check-upstream.py /path/to/pstack-monorepo
    python3 scripts/check-upstream.py /path/to/pstack --out /tmp/report

Exit status: 0 on a completed check (even when drift is found),
2 on operational failure (bad source, clone failure, timeout).
"""
import argparse
import difflib
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
CLONE_TIMEOUT = 300  # seconds for the shallow clone
DEFAULT_SOURCE = "https://github.com/backnotprop/pstack"

# ---------------------------------------------------------------------------
# Mechanical mapping. Applied in order to a copy of upstream pstack/.
#
# Layer 1 (Cursor -> ZCode): verbatim substitution lists from the ZCode
# port's one-shot scripts (pstack-zcode/scripts/adapt-phase1.py and
# adapt-phase2a.py).
# Layer 2 (ZCode -> opencode): the concept mapping from
# docs/DESIGN-opencode-port.md plus verified conventions (tool names,
# subagent types, paths, dual frontmatter).
# ---------------------------------------------------------------------------

LAYER1_CURSOR_TO_ZCODE = [
    # benny install paths: Cursor automations dir -> ZCode non-scanned automations dir
    (".cursor/automations/benny/skills/", ".zcode/automations/benny/skills/"),
    (".cursor/automations/benny/", ".zcode/automations/benny/"),
    ("<target-repository>/.cursor/automations/benny/", "<target-repository>/.zcode/automations/benny/"),
    (".cursor/automations/", ".zcode/automations/"),
    # benny user-owned config location
    (".cursor/benny/", ".zcode/benny/"),
    # plugin enablement in target repo: Cursor settings -> ZCode workspace config
    (".cursor/settings.json", ".zcode/config.json"),
    # project-local skills dir
    (".cursor/skills/", ".zcode/skills/"),
    ("~/.cursor/skills/", "~/.zcode/skills/"),
    # pstack role config file
    ("~/.cursor/rules/pstack-models.mdc", "~/.zcode/pstack-roles.md"),
    # tool names
    ("Task subagent", "Agent subagent"),
    ("Task tool", "Agent tool"),
    ("Task call", "Agent call"),
    ("Task calls", "Agent calls"),
    ("`Task`", "`Agent`"),
    ("AskQuestion", "AskUserQuestion"),
    # skill authoring built-in
    ("Cursor's built-in `create-skill` skill", "the `skill-creator` skill (from the `skill-creator` plugin)"),
    ("Cursor's built-in `create-skill`", "the `skill-creator` skill (from the `skill-creator` plugin)"),
    ("**create-skill** skill (Cursor's built-in for authoring SKILL.md files)",
     "**skill-creator** skill (from the `skill-creator` plugin, for authoring SKILL.md files)"),
    ("`/create-skill`", "`/skill-creator`"),
    # cloud agents -> background subagents
    ("One Cursor cloud agent per PR", "One background subagent per PR"),
    ("Cursor cloud agent", "background subagent"),
    # Slack actions
    ("configured Cursor Slack actions", "configured Slack MCP tools"),
    ("Prefer configured Cursor Slack actions", "Prefer configured Slack MCP tools"),
    # transcript paths, generalPurpose type name, plugin cache paths
    ("substituting `generalPurpose` skips that read and drifts",
     "substituting `general-purpose` skips that read and drifts"),
    ("`generalPurpose` is the fallback. Never use the built-in `plan` subagent_type; it ignores this skill.",
     "`general-purpose` is the fallback."),
    # plugin-installed skill paths
    ("plugin-installed paths under `~/.cursor/plugins/`",
     "plugin-installed paths under `~/.zcode/cli/plugins/cache/`"),
    # transcript globs
    ("do not glob across `~/.cursor/projects/*/`, that crosses workspace boundaries and reads private chats from unrelated projects",
     "do not glob across other workspaces' session directories, that crosses workspace boundaries and reads private chats from unrelated projects"),
    ("Do not glob across `~/.cursor/projects/*/`; that crosses workspace boundaries and reads private chats from unrelated projects.",
     "Do not glob across other workspaces' session directories; that crosses workspace boundaries and reads private chats from unrelated projects."),
    ("do not glob across `~/.cursor/projects/*/`, that crosses workspace boundaries",
     "do not glob across other workspaces' session directories, that crosses workspace boundaries"),
    ("Don't glob across `~/.cursor/projects/*/`; that reads unrelated private chats.",
     "Don't glob across other workspaces' session directories; that reads unrelated private chats."),
    ("Don't glob across `~/.cursor/projects/*/`. That crosses workspace boundaries and reads private chats from unrelated projects.",
     "Don't glob across other workspaces' session directories. That crosses workspace boundaries and reads private chats from unrelated projects."),
    # transcript directory naming
    ("The system prompt names the workspace's `agent-transcripts/` directory. Use only that path.",
     "Locate the current workspace's session transcripts (ZCode stores session data under `~/.zcode/cli/`). Use only the current workspace's paths."),
    ("the active workspace's `agent-transcripts/` directory (the system prompt names the path; ",
     "the active workspace's session transcripts (stored under `~/.zcode/cli/`; "),
    ("the active workspace's `agent-transcripts/` directory (the system prompt names the path)",
     "the active workspace's session transcripts (stored under `~/.zcode/cli/`)"),
    ("the active workspace's `agent-transcripts/` directory (the system prompt names this path)",
     "the active workspace's session transcripts (stored under `~/.zcode/cli/`)"),
    ("the active workspace's `agent-transcripts/` directory (the system prompt names the path; use that path)",
     "the active workspace's session transcripts (stored under `~/.zcode/cli/`; use only that workspace)"),
    # worktree location example
    ("since a hand-typed `myrepo-worktrees/x` misses one that lives at `.cursor/worktrees/myrepo/x`",
     "since a hand-typed `myrepo-worktrees/x` misses one that agent tooling placed under its own state directory"),
]

LAYER2_ZCODE_TO_OPENCODE = [
    # background spawn phrasing (most specific first)
    ("a background subagent (`run_in_background: true`)",
     "a subagent spawned with `background: true`"),
    ("Background agents cannot see this chat", "Subagents cannot see this chat"),
    ("wipe AskUserQuestion state", "wipe `question` state"),
    # user-question tool
    ("the `AskUserQuestion` tool", "the `question` tool"),
    ("`AskUserQuestion`", "the `question` tool"),
    ("run_in_background: true", "background: true"),
    # task tool (opencode's name for the subagent-spawning tool)
    ("Agent subagent", "subagent via the task tool"),
    ("Agent tool", "task tool"),
    ("Agent calls", "task calls"),
    ("Agent call", "task call"),
    ("`Agent`", "`task`"),
    ("`Read`", "`read`"),
    # question tool option name
    ("allow_multiple: true", "multiple: true"),
    # subagent type names
    # NOTE: the English phrase "general-purpose mechanism" is not a subagent
    # type reference; it is protected in map_text() and restored after.
    ("general-purpose", "general"),
    ("generalPurpose", "general"),
    # agent/skill id normalization (display names are kept in prose)
    ("name: Comment Sicko", "name: comment-sicko"),
    ('subagent_type: "Comment Sicko"', 'subagent_type: "comment-sicko"'),
    ("name: Poteto Mode", "name: poteto-mode"),
    ("code-explorer", "explore"),
    ("`Explore`", "`explore`"),
    ('subagent_type: "Explore"', 'subagent_type: "explore"'),
    # paths: skills, agents, roles file, plugins, MCP
    ("plugin-installed paths under `~/.zcode/cli/plugins/cache/`",
     "plugin paths configured via `plugin` in opencode.json"),
    ("`mcp.servers` in `~/.zcode/cli/config.json` (user scope), then `mcp.servers` in the workspace `.zcode/config.json` (or the `.agents/mcp.json` fallback)",
     "`mcp` in `~/.config/opencode/opencode.json` (user scope), then `mcp` in the project `opencode.json`"),
    ("the `mcp__*` tools", "the MCP tools (named `<server>_<tool>`)"),
    ("~/.zcode/pstack-roles.md", "~/.config/opencode/pstack-roles.md"),
    ("~/.zcode/cli/agents/", "~/.config/opencode/agents/"),
    ("~/.zcode/skills/", "~/.config/opencode/skills/"),
    (".zcode/skills/", ".opencode/skills/"),
    ("stale entries under `~/.zcode/cli/` (`image-cache/`, old `artifacts/`)",
     "stale entries under `~/.local/share/opencode/` (old session DBs, artifacts)"),
    # orchestrate conventions
    ("in the current agent's store (path in the system prompt)",
     "at the repo root (project-local, committed or gitignored per project convention)"),
    ("cross-model review", "cross-type review"),
    ("a dedicated verifier agent (on a different model family than the worker)",
     "a dedicated verifier agent (a different subagent type than the worker)"),
    ("retry on a different model", "retry on a different subagent type"),
    # product name (bot-author strings like "cursor" are intentionally untouched)
    ("ZCode", "opencode"),
]

MAP_RULES = LAYER1_CURSOR_TO_ZCODE + LAYER2_ZCODE_TO_OPENCODE

# Dual frontmatter: every SKILL.md with disable-model-invocation gets the
# opencode V2 autoinvoke opt-out inserted directly after the dmi line.
DMI_RE = re.compile(r"(?m)^(disable-model-invocation: true)\n")
DMI_INSERT = r"\1\nmetadata:\n  opencode/autoinvoke: false\n"

# V2 slash commands: the 5 model-invocable skills get an explicit
# `slash: true` inserted directly after the description line. The V2 TUI
# slash palette only lists skills that set the key explicitly (no default);
# V1 ignores it (and V1 never lists skills in the / palette at all).
SLASH_SKILLS = {"how", "why", "setup-pstack", "typescript-best-practices", "unslop"}
DESC_RE = re.compile(r"(?m)^(description: .*)\n")
SLASH_INSERT = r"\1\nslash: true\n"

# ---------------------------------------------------------------------------
# Semantic port edits: one-off hand edits the mapping cannot reproduce.
# When upstream touches one of these, the mapped diff will show the port's
# own edits as drift; re-apply them by hand after importing.
# Keys are paths relative to this repo's root.
# ---------------------------------------------------------------------------
SEMANTIC = {
    "skills/architect/SKILL.md": "model-name defaults -> subagent type defaults + perspective wording",
    "skills/architect/references/runner-prompt.md": "'each on a different model' -> 'each a different subagent type' wording",
    "skills/arena/SKILL.md": "model-name defaults -> subagent type defaults + cross-judge type wording",
    "skills/automate-me/SKILL.md": "transcript rewrite (SQLite) + question-tool option wording",
    "skills/blast-radius/SKILL.md": "multi-model panel wording -> subagent types",
    "skills/figure-it-out/SKILL.md": "'model family' -> 'subagent type' wording",
    "skills/how/SKILL.md": "model-name defaults -> types + critic types are not read-only in opencode",
    "skills/interrogate/SKILL.md": "per-agent model override wording (agent.<name>.model)",
    "skills/interrogate/references/lead-judgment.md": "'models' -> 'reviewers' consensus wording",
    "skills/poteto-mode/SKILL.md": "model -> subagent-type defaults; deslop/cursor-team-kit/bugbot//loop rewrites; V1 experimental background note",
    "skills/poteto-mode/playbooks/autonomous-run.md": "ZCode cron automations rewritten to an OS-level cron/launchd wake",
    "skills/poteto-mode/playbooks/autopilot-full.md": "cloud-sleeper wake -> scheduled automation; cursor-team-kit -> browser-use; deslop -> unslop",
    "skills/poteto-mode/playbooks/autopilot-stack.md": "cloud-sleeper wake -> scheduled automation; deslop -> unslop; cloud division-of-labor wording",
    "skills/poteto-mode/playbooks/babysit.md": "bugbot -> review-bot wording; /loop -> scheduled automation (Cron); cloud+local -> parallel",
    "skills/poteto-mode/playbooks/bug-fix.md": "/loop -> scheduled automation (Cron); model -> role defaults",
    "skills/poteto-mode/playbooks/eval.md": "transcript rewrite (SQLite) + model -> subagent-type wording",
    "skills/poteto-mode/playbooks/feature.md": "model -> role defaults",
    "skills/poteto-mode/playbooks/hillclimb.md": "model -> role defaults",
    "skills/poteto-mode/playbooks/opening-a-pr.md": "deslop -> unslop pass",
    "skills/poteto-mode/playbooks/orchestrate.md": "cloud environment -> background subagents; Cursor dashboard -> task output; store location",
    "skills/poteto-mode/playbooks/pause-safely.md": "'restart Cursor' -> 'restart the app'",
    "skills/poteto-mode/playbooks/perf-issue.md": "model -> role defaults",
    "skills/poteto-mode/playbooks/refactoring.md": "model -> role defaults",
    "skills/poteto-mode/playbooks/session-pickup.md": "transcript lookup rewritten to the SQLite session DB",
    "skills/poteto-mode/playbooks/shipping.md": "control-ui/cli -> browser-use/shell; /loop -> scheduled automation (Cron)",
    "skills/poteto-mode/playbooks/visual-parity.md": "control skill -> browser-use; /loop -> scheduled automation (Cron)",
    "skills/poteto-mode/playbooks/worktree-cleanup.md": "Cursor app-support cache paths -> opencode state paths",
    "skills/poteto-mode/references/bugbot-triage.md": "added 'Bugbot' definition sentence (Cursor's Bugbot, opencode's code-review agents)",
    "skills/poteto-mode/references/plan.md": "model -> type defaults; control skills -> browser-use/shell; deslop -> unslop; babysit skill -> playbook",
    "skills/poteto-mode/scripts/worktree-audit.sh": "transcript lookup rewritten to the SQLite session DB",
    "skills/poteto-mode/scripts/watch-pr/github.ts": "env-configurable bot author/automation id (PSTACK_PR_AUTHOR, PSTACK_AUTOMATION_ID)",
    "skills/recall/SKILL.md": "transcript storage rewritten from JSONL rollouts to opencode's SQLite session DB",
    "skills/reflect/SKILL.md": "transcript rewrite (SQLite) + reviewer fan-out/type wording",
    "skills/setup-pstack/SKILL.md": "rewritten for opencode built-ins + optional per-role model step",
    "skills/show-me-your-work/SKILL.md": "transcript rewrite (SQLite) + cross-type (not cross-model) review wording",
    "skills/swarm/SKILL.md": "cloud workers -> background subagents + model -> type spawn config",
    "skills/why/SKILL.md": "MCP discovery rewritten for opencode + model/readonly lines -> type wording",
    "agents/poteto-agent.md": "is_background -> mode: all frontmatter + task_id resume sentence",
    "agents/comment-sicko.md": "mode: subagent frontmatter",
}


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def run(cmd: list, timeout: int) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        die(f"timed out after {timeout}s: {' '.join(cmd)}")
    except subprocess.CalledProcessError as e:
        die(f"command failed: {' '.join(cmd)}\n{e.stderr.strip()}")


def resolve_upstream_pstack(source: str, tmp: pathlib.Path) -> pathlib.Path:
    """Return the upstream pstack dir (must contain skills/)."""
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", source) or source.startswith("git@") or source.endswith(".git"):
        dest = tmp / "clone"
        run(["git", "clone", "--depth", "1", source, str(dest)],
            timeout=CLONE_TIMEOUT)
        # in backnotprop/pstack (the original repo) pstack lives at the clone root
        pstack = dest
    else:
        base = pathlib.Path(source).expanduser().resolve()
        if (base / "pstack" / "skills").is_dir():
            pstack = base / "pstack"
        elif (base / "skills").is_dir():
            pstack = base
        else:
            die(f"{source!r} is not a monorepo checkout (no pstack/skills/) "
                f"nor a pstack dir (no skills/)")
    if not (pstack / "skills").is_dir():
        die(f"upstream pstack dir has no skills/: {pstack}")
    return pstack


_PROTECTED = "\x00protect\x00"


def map_text(text: str, is_skill_md: bool, skill_name: str = "") -> str:
    # protect English phrases the type-name mapping must not touch
    text = text.replace("general-purpose mechanism", _PROTECTED)
    for old, new in MAP_RULES:
        if old in text:
            text = text.replace(old, new)
    text = text.replace(_PROTECTED, "general-purpose mechanism")
    if is_skill_md:
        text = DMI_RE.sub(DMI_INSERT, text)
        if skill_name in SLASH_SKILLS:
            text = DESC_RE.sub(SLASH_INSERT, text, count=1)
    return text


def map_upstream(pstack: pathlib.Path, mapped: pathlib.Path) -> None:
    """Copy upstream skills/ + agents/ into mapped/ and apply the mapping."""
    for sub in ("skills", "agents"):
        src = pstack / sub
        if src.is_dir():
            shutil.copytree(src, mapped / sub)
    for p in sorted(mapped.rglob("*")):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: leave as-is
        is_skill_md = p.name == "SKILL.md"
        new = map_text(text, is_skill_md, p.parent.name if is_skill_md else "")
        if new != text:
            p.write_text(new, encoding="utf-8")


def rel_files(root: pathlib.Path) -> set:
    if not root.is_dir():
        return set()
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def unified_diff(a: str, b: str, label_a: str, label_b: str) -> str:
    lines = difflib.unified_diff(
        a.splitlines(), b.splitlines(),
        fromfile=label_a, tofile=label_b, lineterm="")
    return "\n".join(lines) + "\n"


def file_text(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Diff upstream pstack (after the port's mechanical mapping) "
                    "against this repo and report drift.")
    ap.add_argument("source", nargs="?", default=DEFAULT_SOURCE,
                    help=f"git URL (default {DEFAULT_SOURCE}), a local monorepo "
                         "checkout, or a local pstack dir")
    ap.add_argument("--out", default=str(REPO / "drift-report"),
                    help="directory for per-item .diff files (default: <repo>/drift-report/)")
    args = ap.parse_args()
    out = pathlib.Path(args.out).expanduser().resolve()

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pstack-drift-"))
    try:
        pstack = resolve_upstream_pstack(args.source, tmp)
        mapped = tmp / "mapped"
        mapped.mkdir()
        map_upstream(pstack, mapped)

        # Upstream commit, when available (clone or local checkout).
        commit = "?"
        try:
            commit = subprocess.run(
                ["git", "-C", str(pstack), "rev-parse", "--short", "HEAD"],
                check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            pass

        # ---- classify items ------------------------------------------------
        results = []  # (kind, name, status, diff_text, semantic_reasons)
        for kind, item_is_dir in (("skills", True), ("agents", False)):
            up_root = mapped / kind
            repo_root = REPO / kind
            if item_is_dir:
                up_names = {p.name for p in up_root.iterdir() if p.is_dir()} if up_root.is_dir() else set()
                repo_names = {p.name for p in repo_root.iterdir() if p.is_dir()} if repo_root.is_dir() else set()
            else:
                up_names = {p.name for p in up_root.iterdir() if p.is_file()} if up_root.is_dir() else set()
                repo_names = {p.name for p in repo_root.iterdir() if p.is_file()} if repo_root.is_dir() else set()
            for name in sorted(up_names | repo_names):
                up_dir = up_root / name
                repo_dir = repo_root / name
                if name in up_names and name not in repo_names:
                    status = "ADDED-UPSTREAM"
                elif name in repo_names and name not in up_names:
                    status = "PORT-ONLY"
                else:
                    status = None  # decided below
                # (label, upstream path or None, repo path or None) per file
                if item_is_dir:
                    up_files = rel_files(up_dir)
                    repo_files = rel_files(repo_dir)
                    pairs = [
                        (f"{kind}/{name}/{rel}",
                         up_dir / rel if rel in up_files else None,
                         repo_dir / rel if rel in repo_files else None)
                        for rel in sorted(up_files | repo_files)]
                else:  # agent item is a single file
                    pairs = [(f"{kind}/{name}",
                              up_dir if up_dir.is_file() else None,
                              repo_dir if repo_dir.is_file() else None)]
                diff_parts = []
                for label, up_p, repo_p in pairs:
                    la = f"upstream (mapped): {label}"
                    lb = f"repo: {label}"
                    if up_p is not None and repo_p is not None:
                        a, b = file_text(up_p), file_text(repo_p)
                        if a != b:
                            diff_parts.append(unified_diff(a, b, la, lb))
                    elif up_p is not None:
                        diff_parts.append(unified_diff(file_text(up_p), "", la, "/dev/null"))
                    else:
                        diff_parts.append(unified_diff("", file_text(repo_p), "/dev/null", lb))
                if status is None:
                    status = "CHANGED" if diff_parts else "UNCHANGED"
                semantic_reasons = [
                    SEMANTIC[label] for label, _, _ in pairs if label in SEMANTIC]
                results.append((kind, name, status, "\n".join(diff_parts), semantic_reasons))

        # ---- write diff files ----------------------------------------------
        out.mkdir(parents=True, exist_ok=True)
        # stale diffs from a previous run
        for stale in out.glob("*.diff"):
            stale.unlink()
        diff_count = 0
        for kind, name, status, diff_text, _ in results:
            if status == "UNCHANGED" or not diff_text:
                continue
            (out / f"{kind}-{name}.diff").write_text(diff_text, encoding="utf-8")
            diff_count += 1

        # ---- console report --------------------------------------------------
        def counts(kind):
            c = {"UNCHANGED": 0, "CHANGED": 0, "ADDED-UPSTREAM": 0, "PORT-ONLY": 0}
            for k, _, s, _, _ in results:
                if k == kind:
                    c[s] += 1
            return c

        print("pstack upstream drift check")
        print(f"  source:   {args.source}")
        print(f"  upstream: {pstack} (commit {commit})")
        print(f"  repo:     {REPO}")
        print()
        for kind in ("skills", "agents"):
            c = counts(kind)
            print(f"  {kind}: {c['UNCHANGED']} unchanged, {c['CHANGED']} changed, "
                  f"{c['ADDED-UPSTREAM']} added-upstream, {c['PORT-ONLY']} port-only")
        print()
        print(f"  diffs written to {out} ({diff_count} file(s))")
        print()
        for kind, name, status, _, reasons in results:
            if status == "UNCHANGED":
                continue
            line = f"{status:<15} {kind}/{name}"
            if reasons:
                shown = "; ".join(reasons[:3])
                if len(reasons) > 3:
                    shown += f"; +{len(reasons) - 3} more file(s) (see {kind}-{name}.diff)"
                line += f"  [SEMANTIC] {shown}"
            print(line)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
