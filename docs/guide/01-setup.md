# Set up pstack

In this page you install pstack, pick which subagent types pstack uses, and run your first task. Setup is one command plus a short conversation.

## Install

```text
./install.sh
```

This copies the skills into `~/.config/opencode/skills/` and the agents into `~/.config/opencode/agents/`. Same-named entries are replaced, anything else in those directories is untouched, and re-running is safe. `./install.sh --link` symlinks instead, so edits to the repo are picked up without reinstalling. On opencode2 you can skip the installer and point your `opencode.json` at the repo with `"skills": ["<path-to-repo>/skills"]` instead.

## Pick your subagent roles

Run:

```text
/setup-pstack
```

[`/setup-pstack`](../../skills/setup-pstack/SKILL.md) detects the subagent types available in your session (built-ins like `general`, `explore`, `build`, `plan`, plus pstack's own agents like `poteto-agent`), shows you each role (code delegates, judgment, the review panels), and asks what you want. Answer the questions. It writes `~/.config/opencode/pstack-roles.md`, a small file every pstack skill reads.

opencode runs every subagent on the session model unless its agent file or config sets a model, so what the roles file configures is the subagent type per role - that is where the diversity comes from. Setup can also write per-role model overrides into `opencode.json` if you want them. You only override what you care about. A role with no line in the file keeps the skill's default. To restore a default later, delete that role's line, or just run `/setup-pstack` again.

For a panel role the value is a list, and one subagent runs per entry, so the list length sets the panel size. Setup also configures `swarm workers`, the default type for every `/swarm` worker unless a race names a type for each arm.

## Accept the verification offer, or don't

At the end of setup, `/setup-pstack` looks for a way to prove app behavior in your project, either a `verify-*` skill or an existing harness. If it finds neither, it offers once to generate one with [`/create-verification-skill`](../../skills/create-verification-skill/SKILL.md).

Say yes and it writes `.opencode/skills/verify-<app>/`, a project-local skill that teaches agents to drive your app the way a user does. It proves the skill works once before handing it over. Say no and setup moves on. You can run `/create-verification-skill` yourself any time. [Verify and ship](./06-verify-and-ship.md#create-a-project-verification-skill) covers when it earns its place.

After setup, start a new chat so the skills load fresh.

## Run your first task

Pick something real but small, and describe it the way you'd describe it to a colleague:

```text
/poteto-mode add a --json flag to this command. text output stays byte-identical. verify both.
```

Watch the todo list. The first item is always "read the Principles section". The rest are the matched playbook's steps copied in, the Feature playbook for this prompt. If `/poteto-mode` skips a step, the step stays in the list with `skip: <reason>`, so you can see what it chose not to do.

From here you can type normal follow-ups. `/poteto-mode` is sticky. It stays on for the conversation until you opt out by saying so.

Next: [Route work through `/poteto-mode`](./02-poteto-mode.md).
