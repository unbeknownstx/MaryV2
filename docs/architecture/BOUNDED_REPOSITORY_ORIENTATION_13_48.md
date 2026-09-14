# Bounded Repository Orientation 13.48

MaryV2 13.48 adds a read-only repository map for locating likely source files and symbols before the existing single-file code-change planner is invoked.

The goal is not to create an autonomous software engineer inside Mary Core. It is to solve a narrower problem: a planner should be able to answer "which file/class/function is relevant?" without serializing an entire repository into an LLM prompt.

## `code_repository_map`

`RepositoryMapClient` walks only `FilesystemClient` workspace roots and returns a bounded map of source/configuration files. It extracts lightweight symbols for Python, JavaScript/TypeScript, Swift, and Rust where possible.

The registered tool is:

- category: `code`;
- permission: `SAFE`;
- external access: false;
- mutates state: false;
- execution: false.

## Bounds

- hard ceiling on files scanned;
- hard per-file byte ceiling;
- bounded returned entries;
- bounded symbols per file;
- no source execution;
- symlinks are skipped;
- common vendor/build/cache directories are skipped (`.git`, `.venv`, `node_modules`, `dist`, `build`, caches, etc.).

A query ranks paths and exact symbol matches, allowing Mary to orient toward a likely implementation file before reading that file through the existing controlled code tools.

## Relationship to existing code-change safety

13.48 intentionally leaves the existing mutation chain unchanged:

1. repository map or code analysis finds the relevant file;
2. `CodeChangePlanner` reads bounded exact source and proposes exact replacements;
3. `CodeClient` generates a unified diff and static validation;
4. the proposal carries an original-source SHA to detect concurrent changes;
5. applying the change remains `APPROVAL_REQUIRED` through ToolRegistry;
6. arbitrary shell/code execution is still absent.

This adopts the useful repository-orientation idea from coding agents without adopting their broader autonomous execution authority.
