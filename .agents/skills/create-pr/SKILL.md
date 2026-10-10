---
name: create-pr
description: Prepare, validate, and open a draft GitHub pull request for the current branch using the repository PR definition. Assign the draft to the person who invoked the skill, set the milestone that matches the confirmed ticket, and link that existing project task in Development. Do not add a second project card. Use when the user invokes $create-pr, writes /create-pr, or asks to create or open a draft PR; do not use for PR review, merge, or release work.
---

# Create Draft Pull Request

Open one draft GitHub pull request that accurately represents the committed branch changes and follows `specifications/pull-request-definition.md`.

## Authority and boundaries

Invoking this skill authorizes read-only ticket lookup, running relevant configured pre-commit hooks, pushing the current branch when required, and opening one draft PR. After that draft exists, it authorizes assigning the pull request to the authenticated user who invoked the skill, setting its repository milestone to match the confirmed issue, and linking that issue in the pull request Development section. The confirmed issue remains the only project card. This skill authorizes deleting a project item that is the new pull request, so the board does not show a second card. It also authorizes a narrowly scoped follow-up commit for verified whitespace- or formatting-only fixes produced by pre-commit, but only on paths that were clean before the hooks ran and are part of the PR diff. Never amend, rebase, force-push, stage unrelated or pre-existing changes, edit issue fields, add the pull request to a project, mark a PR ready, or merge.

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

When a confirmed GitHub issue exists, end the body with a closing reference to that issue number:

```markdown
Closes #<issue number>
```

That line is the Development link. Merging the pull request will close the issue. Do not add it when no GitHub issue was confirmed, and do not point it at a different issue. Additional evidence may follow the required sections when useful, but do not replace or rename them.

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
5. Place the draft using the assignment steps below, then verify assignee, milestone, the Development link, and that the pull request is not a project card.
6. Report the PR URL, ticket context used, assignee, milestone, linked issue, confirmation that the existing task remains the only project card, checks actually run and results, any auto-fix commit created, and testing limitations. Keep the report concise.

## Assign the requester and link the existing task

Do this only after the draft pull request exists. The project card stays the confirmed GitHub issue. Do not add the pull request to a project, and do not set Status or Phase on a pull request item.

The milestone comes from that issue. The milestone key is the ticket id without its final `.<number>`: `M1.5` has milestone key `M1`. A title matches that key when it starts with the key and the next character is absent or is not a digit or a dot, so `M1` matches `M1 - Auth & gated registration` and does not match `M10`.

1. Resolve the requester with `gh api user --jq .login` and assign that user with `gh pr edit <number> --add-assignee @me`. Do not hardcode a login. This is the person who invoked the skill.
2. Read the confirmed issue with `gh issue view`, including its number and milestone. Assignee and milestone commands do not need the `project` scope.
3. Set the pull request milestone to the issue's milestone title with `gh pr edit <number> --milestone "<title>"`. If the issue has no milestone, use the single open repository milestone whose title matches the milestone key. If the issue milestone does not match that key, or zero or more than one milestone matches, stop and ask. Do not guess.
4. Confirm the Development link from the body's `Closes #<issue number>` line. The pull request's closing issue must be that confirmed issue. That link is what shows the pull request on the existing task. Leave the issue's project Status and Phase unchanged.
5. Check the project that contains the confirmed issue. If the new pull request is also an item on that project, delete only that pull request item with `gh project item-delete <number> --owner <owner> --id <item-id>`. Keep the issue item. Project commands need the `project` scope. If `gh` reports that the token is missing `project` or `read:project`, leave the open draft in place, keep the assignee and milestone already set, and stop. Report `gh auth refresh -s project` as the blocker. Do not start an interactive login.

A pull request with no confirmed GitHub issue still gets the requester as assignee. Ask which milestone to use, and do not invent a `Closes` line or add a project card.

If a placement command fails after the draft is open, report the pull request URL and the failing command. Do not close or delete the draft to undo a partial placement.

Stop after the verified draft is placed. Do not mark it ready for review, request reviewers, add labels, merge it, edit the linked issue, or modify Jira unless the developer explicitly requests those actions.
