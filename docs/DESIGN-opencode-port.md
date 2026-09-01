# pstack → opencode port - design

Data: 2026-08-31
Source: the pstack ZCode port (this repo's base; upstream [cursor/plugins/pstack](https://github.com/cursor/plugins/tree/main/pstack) v0.14.1, MIT, by Lauren Tan (poteto)). Pristine baseline committed before any change (see git history).

## Goal

Make the repo a standalone, installable, generic opencode port: 44 skills (5 model-invocable, 39 manual-only), 4 agents (`poteto-agent`, `comment-sicko`, `code-reviewer`, `code-architect`), installable on both opencode V1 and opencode2 (beta), with the manual-only distinction honored wherever the harness can honor it.

## Approach: fork of the ZCode port, minus the harness packaging

The ZCode port already had the hard content adaptation done: `task` tool spawning with explicit subagent types, `question` for user prompts, SQLite transcript storage at `~/.local/share/opencode/opencode.db`, per-role roles file. This pass removes the ZCode/Cursor packaging (`.cursor-plugin/`, `.zcode-plugin/`, `marketplace.json`, the `adapt-phase*.py` scripts) and replaces it with what opencode actually needs: a directory-based installer (`install.sh`) and an opt-in V1 strictness snippet (`snippets/v1-manual-only.jsonc`).

Alternatives rejected:

1. **V2-only `skills: [...]` config, no installer** - rejected: V1 has no `skills` config key and no frontmatter mechanism, so V1 users need the copy/link path anyway. One installer covers both versions.
2. **Keep the ZCode/Cursor manifests** - rejected: dead weight. opencode discovers skills by directory; the manifests would only confuse.

## Concept mapping (ZCode port → opencode)

| ZCode port | opencode |
|---|---|
| Plugin manifest (`.zcode-plugin/plugin.json`) + local marketplace | none; discovery by directory. `install.sh` copies or symlinks `skills/*` → `~/.config/opencode/skills/`, `agents/*.md` → `~/.config/opencode/agents/`. opencode2 additionally accepts `skills: ["<dir-or-url>"]` in `opencode.json` as an alternative to copying |
| `~/.zcode/pstack-roles.md` (roles file) | `~/.config/opencode/pstack-roles.md` (same shape, same on-demand read semantics) |
| Subagent types (`general-purpose`, `Explore`, plugin-contributed types) | opencode built-ins (`build`, `plan`, `general`, `explore`) + pstack's own agents from `agents/` |
| Per-subagent model: not available (session model only) | available: `agent.<name>.model` in `opencode.json`, or `model` frontmatter in the agent file (frontmatter wins). `/setup-pstack` gained an optional per-role model step on top of the type mapping |
| Manual-only skills: frontmatter `disable-model-invocation` ignored by the harness | V1: ignored (all 44 advertised; see gap below). V2: new frontmatter `metadata: opencode/autoinvoke: false` on the 39 manual-only skills |
| Scheduled automations (ZCode's cron tools) | none: opencode has no equivalent, so the overnight/autonomous-run material documents an OS-level wake (a system cron entry or launchd agent running `opencode run` headless) |

### Lesson carried over: diversity by type, not model

The ZCode port's core adaptation - multi-model panels becoming N subagents of the same model differentiated by type and prompt - still holds as the default. opencode *can* run different models per agent, so `/setup-pstack` offers per-role models, but the default stays session-model-everywhere: the skills' postures (reviewer vs architect vs explorer) are what the workflows were designed around.

## V1/V2 dual-targeting strategy

The `skills/` and `agents/` content is harness-neutral text: no V1/V2 branching inside skill bodies. Version differences are handled at the edges:

1. **Frontmatter is the V2 seam.** The 39 manual-only skills carry both the legacy `disable-model-invocation: true` (harmless on V2, documents intent) and `metadata: opencode/autoinvoke: false` (honored by V2). V1 ignores both.
2. **The installer is the V1 seam.** Both versions find skills/agents in the same directories; `install.sh` targets them.
3. **The snippet is the V1 strictness seam** (below).
4. **Slash commands are explicit on V2.** The current opencode2 beta lists a skill in the TUI's `/` palette only when its frontmatter sets `slash: true` (no default is applied when the key is omitted, despite the docs claiming a default of true). The 5 model-invocable skills set it and appear as `/` commands; the 39 manual-only ones do not and are reached via the `/skills` dialog. V1 ignores the key and never lists skills in the `/` palette (the TUI filters skill-sourced commands out by design); use the `/skills` dialog or ask in chat.

## The V1 manual-only gap, and the snippet

V1 advertises every installed skill to the model; there is no frontmatter mechanism to opt a skill out. Its only mechanism is per-agent skill permission: `permission: { "skill": { "<name>": "deny" } }` hides a skill from the model's advertised list while explicit user invocation (`/<name>`) still works.

`snippets/v1-manual-only.jsonc` generates that deny list for exactly the 39 manual-only skills (names taken from each skill's frontmatter `name`, verified equal to the directory name for all 44). It is opt-in, per-agent (the snippet shows `build`, the primary agent; users repeat the block for other primary agents), a no-op on opencode2, and removing a line re-exposes that skill.

## What was skipped

- `automations/benny/` - Cursor scheduled-automation config, kept in the repo for reference. No opencode equivalent today; the natural future is a system cron entry calling `opencode run` with benny's prompts.
- `scripts/adapt-phase1.py`, `scripts/adapt-phase2a.py` - one-shot porting scripts from the ZCode pass; their work is committed, the scripts are not needed.
- Plugin manifests and marketplace (see approach).

## Known interactions

- Users who already have `tdd` or `teach` skills in `~/.config/opencode/skills/` (or project skill dirs) will have pstack's copies overwrite them on install, since the installer replaces same-named entries. That is intended (pstack's are the ported flavors), but it is a merge with overwrite semantics, not a union.
- All 44 skills + 4 agents enter the global skill/agent list (same footprint as superpowers on V1; 39 hidden from the model on V2).

## Install (end user)

1. `./install.sh` (copy) or `./install.sh --link` (symlink).
2. Restart opencode.
3. Optional: `/setup-pstack` for per-role types and models.
4. Optional on V1: merge `snippets/v1-manual-only.jsonc` into `opencode.json`.
5. opencode2 alternative: `"skills": ["<repo>/skills"]` in `opencode.json` instead of the installer.

## Verification

- `bash -n install.sh` clean; installer tested against a scratch prefix: 44 skills + 4 agents installed, foreign entries untouched, `--link` mode produces working symlinks, re-run is idempotent.
- `snippets/v1-manual-only.jsonc` parses after comment stripping (`python3 -m json.tool`); 39 entries, all `deny`.
- Frontmatter `name` equals the directory name for all 44 skills (checked programmatically).
- `rg -i "zcode|cursor" . -g '!skills/' -g '!agents/'` leaves only intentional historical references: this doc's lineage note, the README's, and `automations/benny/` (kept for reference, not ported). Inside skills/agents the survivors are all final skill content: `watch-pr`'s `PSTACK_PR_AUTHOR` default `zcode`, `ZCODE_AUTOMATION_ID`/`CURSOR_AUTOMATION_ID` markers, and bot-author detection for `cursor`/`zcode` (must keep matching the author names the bots actually push as), the upstream `@cursor-skill/poteto-mode-tools` package name, and GraphQL `endCursor` pagination (false positive).
