# Frontend Guidelines

These instructions apply to the React and TypeScript application in this directory.

## Tests

- Use Vitest and React Testing Library for automated frontend tests.
- Keep a test beside the component or module it covers. Name tests `*.test.ts` or `*.test.tsx`, matching the source language and keeping the subject clear (for example, `App.tsx` and `App.test.tsx`).
- Assert user-visible behavior and accessible interactions rather than component internals. Use accessible roles and names for queries where practical.
- Keep tests deterministic. Mock network or browser boundaries rather than relying on live services or timing-sensitive behavior.

## Implementation

- Follow the existing TypeScript, React, ESLint, and formatting conventions in this app.
- Keep UI behavior explicit and predictable. Business values and decisions must remain reviewable; AI output must not silently confirm or replace them.
- Run `npm run test -- --run` for tests, `npm run lint` for linting, and `npm run build` for type checking and production build validation when relevant to a change.
