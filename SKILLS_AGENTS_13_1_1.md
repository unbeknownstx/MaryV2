# MaryV2 Skills + Agents direction after 13.1.1

There are three different concepts that have previously been called "agents" in this project and they should remain separate:

1. **Development agent** — Codex/other coding assistant following `AGENTS.md`. This edits MaryV2 source but is not part of Mary's runtime identity.
2. **Mary Agency/Autonomy** — Mary's represented goals, intentions, priorities, curiosity, decisions, triggers, scheduler, and bounded autonomous behavior.
3. **Task specialist agent** — a future ephemeral worker created for one task. It is not a character and does not own durable Mary state.

## Current pieces already present

- `mary/skills/registry.py`: bounded capability/workspace catalog with safe defaults.
- `mary/tools`: permissioned external/local operations.
- `mary/orchestration/workspace.py`: temporary task state/evidence.
- `mary/orchestration/orchestrator.py`: deterministic privacy/cost/capability/authority planning.
- `mary/orchestration/execution.py`: bounded execution of selected routes.
- `mary/distributed/nodes.py`: capability-aware compute-node registry.
- `mary/realtime/attention.py`: event/attention queue for deciding what deserves cognition.

This means Mary already has most of the substrate needed for "agents" without creating multiple autonomous personalities.

## Next evolution

A skill should become a manifest describing:

- skill id / label / version;
- enabled/default-safe state;
- handler or provider interface;
- required node capabilities;
- local/cloud/external classification;
- privacy/cost class;
- permission/approval requirements;
- accepted inputs and bounded outputs;
- whether output is observation, evidence, action result, or presentation only.

A task-scoped specialist agent should then be assembled as:

```text
Mary intention / creator task
        -> TaskWorkspace
        -> TaskOrchestrator
        -> temporary SpecialistRole
        -> one or more Skills / Models / Tools / Nodes
        -> provenance-bearing evidence
        -> Mary evaluates / synthesizes
        -> creator approval where required
```

The specialist role never receives direct authority to mutate identity, relationship, developed self, memory, values, or permissions. This keeps the useful modularity of agent systems while preserving the central design rule: **providers and specialists work for Mary; they are not Mary.**
