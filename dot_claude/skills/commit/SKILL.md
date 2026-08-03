---
name: "commit"
description: "Use this skill when the user asks to commit changes, organize commits, review commit boundaries, or create commits that follow the repository's existing message style."
---

# Commit changes by coherent units

Use this skill when committing repository changes.

The purpose is to create clean, meaningful commits that match the repository's existing style.

## Core principle

Commit only coherent change units.

A commit should represent one complete and reviewable unit of work.

Do not commit every modified file automatically.

Do not commit partial work that has not yet reached a meaningful change unit.

It is acceptable to create zero commits if the current changes do not yet form a complete unit.

## Initial inspection

Before committing, inspect:

- current worktree state
- staged changes
- unstaged changes
- untracked files
- recent commit messages
- relevant diffs

Use commands such as:

    git status --short
    git diff
    git diff --staged
    git log --oneline -n 20

Use the repository state and commit history as the source of truth.

## Change unit definition

A change unit is a set of changes that together complete one meaningful intent.

Examples of valid change units:

- one feature addition
- one bug fix
- one test addition
- one documentation update
- one refactor with no behavior change
- one experiment or evaluation flow
- one cleanup or maintenance task

A change unit should be:

- internally consistent
- independently understandable
- not mixed with unrelated work
- safe to review as one commit
- complete enough that the commit message can describe it honestly

## Do not commit incomplete units

If changes are still exploratory, incidental, half-applied, or too small to describe as a meaningful unit, do not commit them.

Leave them in the worktree.

This applies even if it means creating zero commits.

Do not create vague checkpoint commits such as:

    chore: 作業途中
    feat: 途中まで実装
    fix: 一部修正

Only commit when the change has reached a coherent boundary.

## Splitting commits

If the worktree contains multiple independent change units, split them into separate commits.

Use selective staging as needed.

Prefer:

    git add -p

or explicit path staging.

Do not mix these in one commit unless they are inseparable:

- production code and unrelated documentation
- feature implementation and unrelated cleanup
- refactor and behavior change
- tests for one feature and fixes for another feature
- generated files and source changes, unless the generated files are required outputs of the same unit

If changes overlap in the same file, stage hunks carefully.

If a hunk cannot be safely split, keep the combined change only when it belongs to the same logical unit.

## Commit message style

Before writing a commit message, inspect recent commit history and follow its tone, format, length, and terminology.

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

## Commit workflow

Repeat this process until no commit-worthy change units remain.

### 1. Identify candidate units

Review the diff and group changes by intent.

For each candidate unit, decide whether it is complete enough to commit.

### 2. Stage one unit only

Stage only the files or hunks belonging to one complete unit.

Use selective staging when necessary.

After staging, inspect:

    git diff --staged

Verify that the staged diff forms exactly one coherent unit.

### 3. Leave non-unit changes unstaged

If a change does not belong to the current unit, leave it unstaged.

If a change is incomplete and not yet commit-worthy, leave it unstaged.

Do not force it into a nearby commit.

### 4. Commit the staged unit

Create one commit with a message matching the repository style.

### 5. Reassess remaining changes

After committing, inspect the worktree again.

If another complete unit exists, commit it separately.

If only incomplete or non-unit changes remain, stop without committing them.

## Safety checks

Before each commit, ensure:

- staged changes are intentional
- no unrelated changes are staged
- no secrets are included
- no temporary files are included
- generated files are included only when they belong to the same unit
- the commit message accurately describes the staged diff

If validation is relevant and reasonably available, run the targeted check for the unit before committing.

If validation is not run, mention that in the final response.

## Final response

When done, report:

- commits created, with commit messages
- changes intentionally left uncommitted
- reason any remaining changes were not committed
- validation commands run, if any

If zero commits were created, say so clearly and explain that no complete change unit was present.
