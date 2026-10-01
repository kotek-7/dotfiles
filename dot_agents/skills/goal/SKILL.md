---
name: goal
description: Use this skill when the user gives a broad development, research, refactoring, debugging, implementation, experimentation, evaluation, or cleanup goal that may require multiple work cycles, commits, and feedback loops until the goal is achieved.
---

# Goal-driven long-running work

You are working toward a user-defined goal over multiple iterations.

Use this skill when the user gives a goal rather than a single narrow edit, especially when the task may require implementation, experiments, evaluation, cleanup, planning, or multiple commits.

## Core principle

Work as an autonomous engineering loop.

Do not merely make one pass. Continue cycling through:

1. understand the current state
2. define the next small objective
3. implement or experiment
4. evaluate the result
5. clean up
6. commit at an appropriate granularity
7. update the plan
8. continue until the goal is achieved or a clear blocker is found

The user’s original goal is the unit of completion.

A commit is only a checkpoint.

## Initial behavior

Before editing, inspect the repository enough to understand:

- project purpose
- current architecture
- test, lint, build, and run commands
- existing conventions
- recent commit message style
- worktree cleanliness

Use existing files and commit history as the source of truth.

If the user’s goal is ambiguous, make the most reasonable interpretation and proceed.

Ask only when proceeding would likely cause harmful or irreversible work.

## Goal definition

Restate the goal internally as:

- desired outcome
- observable completion criteria
- likely validation commands
- known risks or unknowns

Keep a lightweight working plan. Update it as evidence changes.

Prefer concrete completion criteria such as:

- tests pass
- feature behavior is demonstrated
- bug is reproduced and fixed
- benchmark or experiment result is recorded
- documentation or cleanup is completed
- no unrelated diffs remain

## Persistence rule

Treat the user’s goal as the unit of completion, not a single task, file edit, test run, or commit.

A commit is only a checkpoint.

After every checkpoint, continue looking for the next useful action until the original goal is satisfied.

If the goal is broad, decompose it repeatedly.

When one subgoal is complete, choose the next subgoal.

Do not ask the user whether to continue unless the next action requires a decision that cannot be reasonably inferred from the goal.

## Work loop

Repeat the following loop.

### 1. Select the next objective

Choose a small objective that moves directly toward the goal.

The objective should usually fit in one logical commit.

Avoid starting several unrelated changes at once.

### 2. Make the change

Implement, refactor, experiment, document, or clean up as needed.

Respect the existing style and architecture.

Prefer minimal, coherent changes over broad rewrites.

### 3. Validate

Run the most relevant available checks.

Examples:

- unit tests
- integration tests
- type checks
- lint
- build
- formatter
- targeted reproduction commands
- benchmarks or evaluation scripts

If full validation is expensive, run targeted validation first, then broader validation at milestones.

Record important commands and results in the working notes or final summary.

### 4. Review the diff

Before committing, inspect the diff.

Check that:

- the change is scoped
- generated or temporary files are excluded
- no secrets are included
- formatting is acceptable
- behavior matches the current objective
- unrelated edits are reverted or separated

### 5. Commit

Commit when the diff forms a coherent unit of progress.

Do not wait until the entire broad goal is complete if a meaningful subgoal has been achieved.

Do not commit broken work unless it is explicitly useful as a checkpoint and the commit message clearly says so.

Before writing a commit message, inspect recent commit history and follow its tone, format, length, and prefix conventions.

Use commands like:

    git log --oneline -n 20

Commit messages must follow the style of recent commits, with one correction:

- use a general English Conventional Commit-style prefix
- do not use Japanese prefixes such as `修正:` or `検証:`
- write the subject body in Japanese
- keep the message to one line unless a body is clearly needed

Preferred prefixes:

- `feat:` for new features, new commands, new schemas, new generation logic, new evaluation flows
- `fix:` for bug fixes, required field changes, incorrect defaults, broken behavior
- `doc:` for documentation, procedures, glossary, research-flow text, review instructions
- `test:` for tests and reproducibility checks
- `refactor:` for behavior-preserving restructuring
- `chore:` for maintenance that does not fit the above

Tone and format:

- Format: `<prefix>: <日本語の要約>`
- Keep the summary short and specific.
- Prefer noun phrases ending with `を追加`, `を強化`, `を整理`, `を必須化`, `を変更`, `を修正`.
- Mention the concrete target first, then the action.
- Use existing domain terms as-is, including English terms such as `preview`, `writer profile`, `JSONL prior`, `CLI`, `schema`, `baseline`, `report`.
- Avoid overly explanatory messages.
- Avoid vague summaries such as `いろいろ修正`, `改善`, `対応`.
- Avoid Japanese prefixes such as `修正:`, `検証:`, `整理:`.

Examples matching this repository style:

    feat: preview比較コマンドを追加
    feat: writer-profile MVP を追加
    feat: JSONL priorからwriter profileを推定する最小実装を追加
    feat: data-driven priorの実験評価を追加
    fix: data-driven prior評価の既定入力を支持済みセットに変更
    fix: 実験レコードに report を必須化
    doc: human review response の検証手順を追加
    doc: 研究フロー文書と用語集を整備
    test: baseline の再現性テストを追加
    refactor: 修正ループの要約処理を整理
    chore: 実験用出力の管理設定を更新

### 6. Continue by default

After each commit, reassess the goal.

The default action is to continue working.

Do not stop merely because:

- one implementation step is complete
- one commit was created
- some tests pass
- an intermediate milestone was reached
- the current plan items are exhausted
- the remaining work is cleanup, evaluation, documentation, or planning

If the current plan is exhausted but the goal is not clearly achieved, create a new short plan and continue.

Before stopping, explicitly verify all completion criteria.

Stop only when one of these is true:

- the goal is achieved and validated
- there is a concrete blocker that cannot be resolved without user input
- continuing would require credentials, paid services, destructive operations, or external permissions
- the repository is in a state where safe progress is impossible
- the user explicitly instructed to stop after a limited amount of work

When stopping because of a blocker, leave the repository in a clean and useful state if possible.

## Planning discipline

Maintain a concise plan.

The plan should have only the next few meaningful steps, not a speculative full roadmap.

Update the plan whenever:

- a step is completed
- validation fails
- the implementation direction changes
- new information invalidates the previous plan

When the current plan is complete but the original goal is not complete, create a new short plan and continue.

## Feedback loop

Use feedback from:

- tests
- compiler or type errors
- lint results
- runtime behavior
- logs
- benchmark results
- existing issues or TODOs
- user instructions
- code review from the diff itself

Treat failed validation as useful feedback. Diagnose and iterate.

Do not hide failures. Summarize the failure, the likely cause, and the next corrective action.

## Experiments

When experimenting:

- isolate experimental changes when possible
- keep notes on what was tried
- preserve only useful results
- remove dead experiments before committing unless they are intentionally documented
- commit experiment infrastructure separately from production behavior when appropriate

## Cleanup

Before finalizing:

- remove temporary files
- remove debug prints unless intentionally kept
- ensure docs or comments match behavior
- ensure tests reflect intended behavior
- check `git status`
- run the broadest reasonable validation available

## Pre-final checklist

Before giving a final response, verify:

- Is the original user goal actually achieved?
- Were all known validation steps run or intentionally skipped with a reason?
- Are there remaining obvious implementation, evaluation, cleanup, or documentation tasks?
- Is there a next reasonable action that does not require user input?

If there is any reasonable next action, do not final-answer yet. Continue the work loop.

## Final response

When stopping, report:

- whether the goal was achieved
- commits created, with Japanese commit messages
- validation commands run and their results
- remaining blockers or follow-up work, if any

Keep the final response concise and factual.
