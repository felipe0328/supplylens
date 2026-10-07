---
name: create-pr
description: Prepare, validate, and open a draft GitHub pull request for the current branch using the repository PR definition. Use when the user invokes $create-pr, writes /create-pr, or asks to create or open a draft PR; do not use for PR review, merge, or release work.
---

# Create Draft Pull Request

Open one draft GitHub pull request that accurately represents the committed branch changes and follows `specifications/pull-request-definition.md`.

## Authority and boundaries

Invoking this skill authorizes read-only ticket lookup, running relevant configured pre-commit hooks, pushing the current branch when required, and opening one draft PR. It also authorizes a narrowly scoped follow-up commit for verified whitespace- or formatting-only fixes produced by pre-commit, but only on paths that were clean before the hooks ran and are part of the PR diff. Never amend, rebase, force-push, stage unrelated or pre-existing changes, modify tickets, mark a PR ready, or merge.

Read the repository-root `AGENTS.md` and `specifications/pull-request-definition.md` before drafting. Those files remain authoritative if this workflow and repository policy differ.

## Establish the change set

1. Collect branch, status, remotes, upstream, remote default branch, and existing-PR state in one batched inventory where tools permit.
2. Resolve the base branch from the remote default. Ask the developer when the base is missing or ambiguous.
3. Review the complete `<base>...HEAD` commit list and diff once. Check staged/unstaged paths; read their full diffs only when they overlap the PR or affect whether it can safely proceed.
4. Never include existing working-tree changes in the PR. If material uncommitted changes exist, ask whether to proceed with committed changes only. The pre-commit auto-fix exception below applies only to hook-produced formatting changes.
5. If a PR already exists for the head branch, do not create a duplicate. Report its URL and state; update it only if the developer explicitly requests an update.

## Resolve ticket and intention

The ticket id comes from the branch name, then must be confirmed against GitHub before it is written into the title. GitHub issue titles use a dotted task id such as `M1.1`. Branch names use an underscore in that position, so `M1_1` is the branch for `M1.1`.

1. Read the current branch name.
2. When the branch is `M<number>_<number>`, form a candidate by replacing that underscore with a dot (`M1_1` becomes `M1.1`).
3. Search repository issues with `gh issue list --search "<candidate> in:title"`. Use the candidate only when exactly one issue title starts with it, and copy the id from that title. Do not put the raw branch spelling in the title.
4. If issue search returns no starting match, more than one starting match, or cannot be run, stop and ask the developer which ticket id to use. Do not guess. A GitHub Projects board can confirm the same id when `gh project` is authorized; lack of project scope is not a reason to skip the issue search.
5. A branch that does not match `M<number>_<number>` is not one of these task ids. A single key shaped like `ABC-123` may be used when a Jira lookup confirms that exact key. Otherwise ask the developer when a ticket is required. If no ticket exists and the changes still establish a clear intention, continue without a ticket segment.

Use the branch diff and commit history as the primary evidence for what changed and why:

- When a Jira lookup confirms a candidate, read the ticket and use its summary, description, and acceptance criteria as supporting context. Do not change Jira.
- If the confirmed ticket and the changes disagree, or the PR intention remains materially unclear, stop and ask for clarification.

## Draft the title and body

Choose the single lowercase prefix that best represents the primary change. Follow the title format from the PR definition:

```text
[<TICKET>] <prefix>: <imperative summary>
```

Use a prefix such as `feat`, `fix`, `minor`, or `major`. The bracketed value is the confirmed GitHub task id, such as `M1.1`, not the branch spelling `M1_1`. Omit the ticket segment only when no ticket is established. Do not invent a ticket, test result, business motivation, or acceptance criterion.

Build the PR body with the exact required structure:

```markdown
## Summary

<PR intention, problem, expected outcome, and important scope boundaries>

## Testing

### Unit testing

<commands and results, or Not applicable with a reason>

### Manual testing

<scenarios and results, or Not run/Not applicable with a reason>

## Rollback plan

<safe, actionable reversal steps>
```

Additional evidence may follow these sections when useful, but do not replace or rename them.

## Pre-commit gate

Run this gate after the proposed PR content is known and immediately before pushing or opening the PR. Batch independent read-only checks and reuse the established diff and test evidence instead of repeating it:

1. Recheck the branch, base, status, commits, and full diff.
2. Run `git diff --check <base>...HEAD`, `git diff --check`, and `git diff --cached --check`. Check changed files for conflict markers; fail on any whitespace errors, unresolved markers, or malformed patches.
3. Inspect the diff for credentials, private supplier or customer information, private pricing policies, generated artifacts, and accidental unrelated files.
4. When `.pre-commit-config.yaml` exists, run `pre-commit run --files <changed PR files>` using existing files from `<base>...HEAD`. Run `--all-files` only when the PR changes the hook configuration or a repository-wide rule requires it. If pre-commit is unavailable or cannot complete, treat the gate as failed.
5. Record the worktree state before hooks. If hooks fail after applying fixes, inspect the exact resulting diff. Automatically stage only paths that were clean before hooks, are in the PR diff, and contain exclusively whitespace/formatting changes (such as trailing whitespace, final newline, or formatter-only output). Commit those exact paths in a separate follow-up commit, rerun pre-commit on them, and continue only if it passes. Never amend. For any other changed path or non-formatting edit, stop and report the diff; do not stage or commit it.
6. Run only additional checks required by the PR definition and not already covered by the changed-file hooks. Use the relevant commands from `AGENTS.md` and the `Makefile`; avoid rerunning broad checks when focused hooks already cover the changed behavior. For database or migration changes, run the applicable migration check and record environment dependencies.
7. Perform practical manual checks when feasible and relevant. Never claim an unperformed check; state `Not run` or `Not applicable` with the reason.

If a required check fails, sensitive data is present, the diff is inconsistent with the ticket, or the rollback is unsafe, do not push or open the PR. Report the blocker and the exact failing command or finding. Do not modify files to fix it unless the developer separately asks for implementation.

## Open and verify the draft PR

1. Confirm GitHub authentication and repository identity using an available GitHub integration or the `gh` CLI.
2. Push the current branch's existing commits to its normal remote if it has no upstream. Never force-push.
3. Create the PR as a draft against the resolved base using the prepared title and body. With `gh`, prefer a temporary body file outside the repository and `gh pr create --draft --base <base> --head <branch> --title <title> --body-file <file>`.
4. Verify the created PR's URL, draft state, base branch, head branch, title, and body. Remove any temporary body file.
5. Report the PR URL, ticket context used, checks actually run and results, any auto-fix commit created, and testing limitations. Keep the report concise.

Stop after the verified draft is open. Do not mark it ready for review, request reviewers, add labels, merge it, or modify Jira unless the developer explicitly requests those actions.
