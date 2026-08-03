---
name: "handoff"
description: "Use when the user wants to transfer the current conversation, task state, project context, decisions, constraints, or next steps to another agent or a new chat. Produces a concise context handoff prompt that another agent should read before waiting for the user's next instruction."
---

# Handoff

Use this skill to turn the current conversation and task state into a prompt that another agent can use to understand the context before waiting for the user's next instruction.

## Principles

- Output a standalone prompt addressed to the next agent.
- Include only information needed to continue the work.
- Separate confirmed facts from assumptions and unresolved questions.
- Preserve user preferences, constraints, and safety rules that affect future actions.
- The handoff prompt must not instruct the next agent to start editing, running commands, or continuing implementation automatically.
- The next agent should only absorb the context and wait for the user's explicit next instruction.
- Do not include hidden chain-of-thought, internal deliberation, or irrelevant conversation history.
- Do not expose secrets, tokens, credentials, private keys, or sensitive file contents.
- If sensitive context matters, describe its existence and location generically instead of copying values.

## Workflow

1. Identify the target handoff scope.
   - Current task only, whole conversation, project setup, debugging state, implementation state, or review state.
   - If the user does not specify, assume the current task and immediately relevant project context.
2. Extract continuation-critical context.
   - User goal.
   - Repository/path and environment.
   - Relevant files inspected or changed.
   - Commands run and important outcomes.
   - Decisions made and rationale.
   - Constraints from `AGENTS.md` or user instructions.
   - Current status, blockers, and next steps.
3. Normalize the result.
   - Remove apology, process chatter, and stale branches of discussion.
   - Keep dates, versions, paths, and command names concrete.
   - Mark uncertain details as assumptions.
4. Produce a paste-ready prompt.
   - Prefer one fenced text block.
   - The prompt should tell the next agent to read the context and wait.
   - List possible next steps as options or likely follow-up areas, not as commands to execute.
   - Include a short "Do not" section for important safety constraints.
   - After outputting the handoff prompt, stop. Do not begin any work described inside the handoff.

## Output Template

```text
You are receiving context for an existing task.

Read this context only. Do not edit files, run commands, or continue implementation until the user gives an explicit next instruction.

Goal:
- ...

Context:
- Working directory: ...
- Environment: ...
- Relevant project instructions: ...

What has already been done:
- ...

Files changed:
- ...

Important findings:
- ...

Current status:
- ...

Possible next steps:
- ...

Constraints and cautions:
- ...

Wait for the user's next instruction before taking action.
```

When no files were changed, write `Files changed: none`.
