# MaryV2 Autonomy Preservation Note

This note records the post-13.2 lifecycle preservation pass for the existing
autonomy subsystem.

- `AutonomyRuntime` existed before this change.
- This pass does not introduce a new autonomy architecture.
- It connects the existing `AutonomyRuntime` lifecycle to the canonical
  `MaryApplication`.
- Each successful canonical turn may produce one bounded, observable autonomy
  cycle result.
- Autonomous actions remain proposals only and require explicit approved
  execution elsewhere.
- No external action broker has been connected in this pass.
- No pre-cloud `/data` state was modified.
- Meaningful agency/curiosity trigger registration remains a subsequent
  integration task.
