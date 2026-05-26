---
name: "explain"
description: "Use when the user asks to explain the project in the current working directory, summarize what this repository does, describe its structure, or provide a user-facing project overview. This skill performs read-only inspection and returns a concise explanation for the user."
metadata:
  short-description: "Explain the current project"
---

# Explain

Use this skill to explain the project at the current working directory to the user. This is different from onboarding: the goal is not only to orient the agent, but to produce a clear user-facing explanation.

## Scope

Explain:

- what the project appears to do
- who or what it is for
- main technologies and frameworks
- important files and directories
- how the code is organized
- how to run, build, and test it when discoverable
- noteworthy constraints, risks, or unclear areas

## Workflow

1. Inspect project instructions first.
   - Read local `AGENTS.md`, `.codex/`, `.agents/`, README files, and central docs when present.
   - Respect project-specific instructions over global assumptions.
2. Identify project type and stack.
   - Check common manifest/config files such as `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `platformio.ini`, `CMakeLists.txt`, `compose.yaml`, and CI workflows.
3. Map structure without over-reading.
   - Prefer `rg --files` and shallow directory listings.
   - Avoid dependency, generated, cache, and build output directories.
4. Read representative files.
   - Inspect entry points, main modules, routes, commands, hardware targets, or app screens depending on the project.
   - Read only what is needed to explain the project accurately.
5. Produce a user-facing explanation.
   - Keep it concise and concrete.
   - Separate confirmed facts from inferences.
   - Mention unknowns only when they matter.
   - Do not edit files unless the user explicitly asks for documentation changes.

## Output

Use this structure when helpful:

- Overview
- Main Stack
- Directory Map
- How It Works
- Run / Build / Test
- Important Files
- Notes and Unknowns

Prefer short sections over long exhaustive analysis. If the user asks for a README-style document, propose a target file and wait for explicit edit approval before creating or modifying files.
