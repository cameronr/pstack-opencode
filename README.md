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

   Copies `skills/*` into `~/.config/opencode/skills/` and `agents/*.md` into `~/.config/opencode/agents/`. Same-named entries are replaced; anything else in those directories is untouched. Safe to re-run. `--prefix DIR` installs elsewhere.

2. **Symlink** (repo edits are picked up without reinstalling):

   ```sh
   ./install.sh --link
   ```

   Symlinks are absolute: moving the repo breaks them. Re-run the installer from the new location.

    **Updating:** re-run the installer after `git pull` - it prunes items removed upstream and leaves your own skills/agents untouched. With `--link`, `git pull` alone suffices.

3. **opencode2 only: point the config at the repo** (no copy at all):

   ```json
   {
     "skills": ["~/code/pstack-opencode/skills"]
   }
   ```

   Local dirs may be absolute, `~`, or project-relative. Use either this config entry or the installer, not both. `skills:` covers skills only: the agents still need the installer (`./install.sh` or `./install.sh --link`) or a manual copy of `agents/*.md` into `~/.config/opencode/agents/` (or the project's `.opencode/agents/`).

## Behavior by version

- **V1** advertises all 44 skills to the model; there is no frontmatter mechanism for manual-only skills. If you want the 39 manual-only skills invisible to the model (explicit `/name` invocation still works), merge [snippets/v1-manual-only.jsonc](snippets/v1-manual-only.jsonc) into your `opencode.json`.
- **opencode2** honors the `metadata: opencode/autoinvoke: false` frontmatter in the 39 manual-only skills, so they stay out of the model's advertised list and appear in the command catalog instead. The V1 snippet is a no-op there.

## Setup

Run the `setup-pstack` skill (`/setup-pstack`). It detects the agent types available in your session, maps each pstack role (code delegates, judgment, the review panels) to a type, and writes `~/.config/opencode/pstack-roles.md`, the override layer the skills read. It can also set per-role models in `opencode.json` if you want them.

## Syncing with upstream

This repo is a port of [cursor/plugins/pstack](https://github.com/cursor/plugins/tree/main/pstack). The port applied a mechanical convention mapping (tool names, subagent types, paths, dual frontmatter) plus one-off semantic hand edits (transcript rewrites, cloud-agent -> background-subagent rewrites, model -> subagent-type wording). `scripts/check-upstream.py` fetches upstream, applies the mechanical mapping, and diffs the result against this repo, so the report shows only what upstream changed that we have not absorbed:

```sh
python3 scripts/check-upstream.py                          # clone github.com/cursor/plugins (shallow, sparse)
python3 scripts/check-upstream.py /path/to/cursor/plugins  # local checkout (must contain pstack/skills/)
python3 scripts/check-upstream.py /path/to/pstack --out /tmp/report
```

Reading the report (per-file diffs land in `drift-report/`, one `.diff` per skill or agent):

- **ADDED-UPSTREAM** - new upstream skills/agents: candidates to import. Take the mapped file from the diff (or re-run against a local checkout and copy from there), re-apply any semantic edits the port would need, and commit. Skip the ones built on Cursor-only features (e.g. webhook routines).
- **CHANGED** - upstream modified a file we also have. Read the diff; import the upstream change on top of our mapped conventions.
- **CHANGED ... [SEMANTIC]** - the file also carries one-off port edits the mapping cannot reproduce (the script lists them in `SEMANTIC`). When upstream touches one of these, the diff mixes upstream drift with our own edits; re-apply the semantic edits by hand after importing.
- **PORT-ONLY** - in this repo, not upstream. Expected for port additions (`code-reviewer`, `code-architect`); no action.

The check always exits 0 when it completes (drift or not); non-zero means an operational failure (bad source, clone failure).

## Not ported

- `automations/benny/` - a Cursor scheduled-automation config, kept in the repo for reference. opencode has no equivalent today; the natural future is a system cron entry that calls `opencode run` with benny's prompts.
- The Cursor and ZCode plugin manifests (`.cursor-plugin/`, `.zcode-plugin/`, `marketplace.json`) are removed. opencode discovers skills and agents by directory, so no manifest is needed.

## Guide

The full workflow guide - setup, `/poteto-mode`, the understand/design/build/verify pages, overnight runs, principles, recipes - is in [docs/guide/](docs/guide/).
