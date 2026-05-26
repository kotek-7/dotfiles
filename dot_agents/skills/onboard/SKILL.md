---
name: "onboard"
description: "Use when first entering a project or when the user asks to understand, inspect, summarize, onboard, or get familiar with a repository. This skill performs read-only project orientation: structure, stack, important files, commands, tests, docs, risks, and next investigation targets."
metadata:
  short-description: "Read-only project orientation"
---

# Onboard

Use this skill at the start of work in an unfamiliar project. Keep the pass read-only unless the user explicitly asks for changes.

## Scope

Build a concise working model of the project:

- purpose and domain
- tech stack and package/build tools
- repository structure
- important entry points and configuration files
- build, test, lint, run, and deployment commands
- existing documentation and project instructions
- likely risk areas and follow-up questions

## Workflow

1. Read project instructions first.
   - Check `AGENTS.md`, `.codex/`, `.agents/`, README files, and docs that appear central.
   - Treat nearer project instructions as more specific than global instructions.
2. Map the repository structure.
   - Prefer `rg --files` and shallow directory listings.
   - Avoid dumping huge trees or reading generated/dependency directories.
3. Detect the stack.
   - Look for `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `go.mod`, `platformio.ini`, `CMakeLists.txt`, `compose.yaml`, CI workflows, and framework config files.
4. Identify workflows.
   - Extract scripts and commands from package/config files.
   - Prefer documented commands over guessed commands.
   - Note commands that are likely but unverified.
5. Inspect key implementation paths.
   - Read only representative files needed to understand architecture.
   - Identify entry points, routes, services, hardware targets, or CLI commands depending on project type.
6. Summarize without changing files.
   - Keep the summary short and actionable.
   - Separate confirmed facts from inferences.
   - Call out unknowns that materially affect future work.

## Output

Use this structure when useful:

- Project purpose
- Stack and tools
- Important files/directories
- Run/test/build commands
- Architecture notes
- Existing docs/instructions
- Risks or gotchas
- Suggested next steps

If the user asks for a deeper onboarding document, propose the target file and wait for explicit edit approval before creating it.
