# pstack (opencode port)

pstack is a set of rigorous agent workflows: engineering principles, playbooks, and subagents that make an agent work like a senior engineer instead of a code generator. It routes work through `/poteto-mode`, which picks a playbook, runs the other skills as steps, and demands evidence. Ported from [poteto's Cursor original](https://github.com/cursor/plugins/tree/main/pstack) (MIT) via the ZCode port; this repo is a standalone, installable opencode port.

## Contents

- **44 skills** in `skills/`. Five are model-invocable (the model can reach them on its own); 39 are manual-only, meant to be invoked by you or by another skill.
  - Model-invocable: `how`, `setup-pstack`, `typescript-best-practices`, `unslop`, `why`.
  - Manual-only include `/poteto-mode`, `/architect`, `/arena`, `/swarm`, `/interrogate`, `/tdd`, the 21 `principle-*` skills, and the rest.
- **4 agents** in `agents/`: `poteto-agent` (the poteto-mode delegate), `comment-sicko`, `code-reviewer`, `code-architect`.

## Prerequisites

- `bun` - the poteto-mode scripts (`orch`, `watch-pr`).
- `gh` - `worktree-audit`, `watch-pr`, `opening-a-pr`.
- `sqlite3` - the transcript-reading skills (`recall`, `reflect`, `automate-me`, `show-me-your-work`, `session-pickup`, `eval`, `worktree-audit`).
- `gt` (Graphite) - the `orchestrate` playbook.

Some flows route to an external `skill-creator` skill (`reflect`, `automate-me`, `authoring-a-skill`) that is not part of this repo; install it separately if you use those flows.

## Install

Pick one:

1. **Copy** (works on opencode V1 and opencode2):

   ```sh
   ./install.sh
   ```

   Copies `skills/*` into `~/.config/opencode/skills/` and `agents/*.md` into `~/.config/opencode/agent/`. Same-named entries are replaced; anything else in those directories is untouched. Safe to re-run. `--prefix DIR` installs elsewhere.

2. **Symlink** (repo edits are picked up without reinstalling):

   ```sh
   ./install.sh --link
   ```

   Symlinks are absolute: moving the repo breaks them. Re-run the installer from the new location.

3. **opencode2 only: point the config at the repo** (no copy at all):

   ```json
   {
     "skills": ["~/code/pstack-opencode/skills"]
   }
   ```

   Local dirs may be absolute, `~`, or project-relative. Use either this config entry or the installer, not both. `skills:` covers skills only: the agents still need the installer (`./install.sh` or `./install.sh --link`) or a manual copy of `agents/*.md` into `~/.config/opencode/agent/` (or the project's `.opencode/agent/`).

## Behavior by version

- **V1** advertises all 44 skills to the model; there is no frontmatter mechanism for manual-only skills. If you want the 39 manual-only skills invisible to the model (explicit `/name` invocation still works), merge [snippets/v1-manual-only.jsonc](snippets/v1-manual-only.jsonc) into your `opencode.json`.
- **opencode2** honors the `metadata: opencode/autoinvoke: false` frontmatter in the 39 manual-only skills, so they stay out of the model's advertised list and appear in the command catalog instead. The V1 snippet is a no-op there.

## Setup

Run the `setup-pstack` skill (`/setup-pstack`). It detects the agent types available in your session, maps each pstack role (code delegates, judgment, the review panels) to a type, and writes `~/.config/opencode/pstack-roles.md`, the override layer the skills read. It can also set per-role models in `opencode.json` if you want them.

## Not ported

- `automations/benny/` - a Cursor scheduled-automation config, kept in the repo for reference. opencode has no equivalent today; the natural future is a system cron entry that calls `opencode run` with benny's prompts.
- The Cursor and ZCode plugin manifests (`.cursor-plugin/`, `.zcode-plugin/`, `marketplace.json`) are removed. opencode discovers skills and agents by directory, so no manifest is needed.

## Guide

The full workflow guide - setup, `/poteto-mode`, the understand/design/build/verify pages, overnight runs, principles, recipes - is in [docs/guide/](docs/guide/).
