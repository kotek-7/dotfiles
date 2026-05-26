---
name: "sync-doc"
description: "Use when checking consistency between documentation and implementation, including README files, docs directories, API docs, setup steps, file paths, commands, dependencies, and tests. Trigger when the user asks to sync docs with code, find stale documentation, verify docs against implementation, or update docs after code changes."
metadata:
  short-description: "Sync docs with implementation"
---

# Sync Docs

Use this skill to detect and fix inconsistencies between documentation and the actual implementation.

## Workflow

1. Identify the documentation scope.
   - Use user-provided paths first.
   - Otherwise inspect likely docs such as `README.md`, `docs/`, API documentation, setup guides, design notes, and project-specific documentation files.
2. Verify claims against the implementation.
   - Check referenced files and directories.
   - Check scripts, commands, package manager usage, and setup steps.
   - Check dependencies, configuration names, environment variables, and test commands.
   - Check documented APIs, public functions, CLI options, routes, and user-facing workflows.
3. Report findings by severity.
   - Critical: wrong paths, commands, API names, or setup steps that break use.
   - Warning: stale or duplicated documentation that can mislead maintainers.
   - Info: missing documentation or minor drift.
4. Propose focused fixes.
   - Keep changes limited to documentation unless the user explicitly asks for implementation changes.
   - Preserve the existing documentation style and structure.
   - Do not add process notes about the review itself to the docs.
5. Apply changes only after the active repository instructions permit editing.
   - If approval is needed, present the target files and the planned edits first.
   - After editing, rerun the relevant checks or at least re-read changed sections.

## Output

Summarize:

- documentation files inspected
- implementation areas checked
- inconsistencies found
- files changed, if any
- checks performed
