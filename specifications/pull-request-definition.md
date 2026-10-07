# Pull Request Definition

## Status and Purpose

This document is the canonical definition of a SupplyLens pull request. It is intended for human contributors, AI-assisted workflows, and a future custom PR skill. `AGENTS.md` provides the short repository rule; this file provides the complete contract.

A pull request is a reviewable proposal with one coherent purpose. It should be small enough to understand, verify, and reverse without mixing unrelated cleanup or product work.

## Authorization and Ownership

- Creating a branch, staging files, committing, pushing, or opening or updating a pull request requires an explicit developer request.
- AI-authored or AI-modified contributions must not be staged unless the developer explicitly asks for those exact changes to be staged.
- Invoking the repository's create-PR skill explicitly authorizes a separate commit containing only verified whitespace- or formatting-only changes auto-produced by configured hooks, limited to PR-diff paths that were clean before the hooks ran. This does not authorize amending commits or including any pre-existing changes.
- Existing staged and unstaged changes are developer-owned. Do not absorb, rewrite, unstage, discard, or publish them without explicit direction.
- A request to review a change authorizes read-only inspection and feedback only. It does not authorize fixes or Git mutations.
- The developer owns the final scope, message, publication decision, and merge decision.

## Required Scope

Every pull request must:

1. Address one clear feature, fix, documentation change, test improvement, or maintenance goal.
2. Stay within the MVP and architecture boundaries in `docs/`, or explicitly explain a deliberate design change.
3. Avoid unrelated refactors, formatting churn, generated-file noise, and private data.
4. Preserve the no-LLM workflow and deterministic validation and calculations.
5. Include schema migrations with model changes when persistence is affected.
6. Use synthetic or anonymized fixtures and examples only.

If independent changes can be reviewed and released separately, they should be separate pull requests.

## Title

Every pull request must have a clear, non-empty title with exactly one lowercase prefix. When a ticket exists, put its key or number first:

```text
[<TICKET>] <prefix>: <imperative summary>
```

Common prefixes include `feat`, `fix`, `minor`, `major`, `chore`, `bug`, `docs`, `test`, and `refactor`. Use the one prefix that best represents the primary purpose of the PR. Do not combine prefixes.

Examples:

```text
[M1.1] feat: add the user model and password hashing
[M1.2] fix: prevent duplicate purchase totals
[M4.1] minor: expand the purchase report
[M2.1] major: replace the upload API
chore: update local development commands
```

The ticket is preferred but may be omitted when no ticket exists. The summary should be concise, imperative, and specific enough to identify the change without opening the PR. Version automation reads the prefix after the optional ticket: `major` requests a major bump, `feat` and `minor` request a minor bump, and every other prefix requests a patch bump.

## Required Description

Use these headings in this order. Write `None` or `Not applicable` rather than silently omitting a section.

```markdown
## Summary

Describe the intention of the PR, the problem it addresses, and the expected outcome. Include important scope boundaries when needed.

## Testing

### Unit testing

List the automated unit tests and commands run, with their results. If no unit tests apply or exist, state that and explain why.

### Manual testing

List the manual scenarios and commands exercised, with their results. If manual testing does not apply, state that and explain why.

## Rollback plan

Explain how to safely reverse the change. Include migration, configuration, deployment, or data-recovery steps when applicable. If reverting the PR is sufficient, state that explicitly.
```

Additional links, screenshots, risk notes, and implementation details may be included when useful, but they do not replace the required sections above.

## Verification Expectations

Run the narrowest relevant checks and the repository-level checks appropriate to the change. Prefer the root Make targets when available.

- Backend changes: compile or test the affected Python code and exercise relevant API behavior. Database-dependent behavior must include the unavailable-database path where applicable.
- Database changes: run migration checks and test upgrade behavior against a clean local database. Include a reversible downgrade when the migration can safely support one.
- Frontend changes: run lint and production build; add focused component tests once the test framework exists.
- Fixture or extraction changes: verify expected results, provenance, validation failures, and no-LLM operation using synthetic documents.
- Documentation-only changes: check links, paths, commands, and consistency with the implemented repository state.

Do not claim a check passed if it was not run. A known failure must be included with its cause and expected follow-up.

## Review Gates

A pull request is ready for review only when all applicable statements are true:

- The diff matches the stated purpose and contains no accidental files or secrets.
- Behavior and acceptance criteria are clear from the description.
- Relevant validation has passed, or exceptions are plainly documented.
- New behavior has appropriate tests, or the testing gap and reason are explicit.
- Unit and manual testing are reported separately in the PR description.
- The rollback plan is safe, actionable, and accounts for migrations or data changes when applicable.
- Document facts, confirmed records, and policy estimates remain distinct.
- Extracted or AI-generated values cannot bypass human confirmation.
- Currency and decimal behavior remain explicit and deterministic.
- Source provenance and immutable history are preserved where affected.
- Database changes include reviewed migrations and operational notes.
- UI changes include visual evidence and account for narrow layouts when relevant.
- Logs, fixtures, screenshots, and examples contain no supplier, customer, credential, or private-policy data.

## Reviewer Priorities

Review in this order:

1. Product correctness and MVP scope.
2. Privacy, security, and data-loss risk.
3. Provenance, human confirmation, and deterministic behavior.
4. Schema and migration safety.
5. Failure handling and no-LLM operation.
6. Test evidence and maintainability.
7. Naming, style, and documentation clarity.

Blocking findings should identify the affected behavior and the evidence needed to resolve them. Suggestions that are outside the PR purpose should be labeled as non-blocking follow-up work.

## Completion

Approval means the reviewed diff and documented evidence satisfy this definition. It does not authorize an AI agent to merge, push, stage additional files, or make follow-up changes unless the developer explicitly asks for that action.
