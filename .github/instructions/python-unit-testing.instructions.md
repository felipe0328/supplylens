---
description: "Use when writing or updating Python backend unit tests, including co-located pytest files."
applyTo:
	- "apps/backend/tests/unit/*_test.py"
	- "apps/backend/src/**/*_test.py"
---

# Python Unit Testing

These rules apply to Python unit tests only. Integration-test conventions will be defined separately.

- Use `pytest` and keep a unit test beside the implementation file it exercises.
- Name the test file `<script_name>_test.py`; for example, test `storage.py` in `storage_test.py` in the same directory.
- Keep tests focused on observable behavior, including success paths, validation failures, and relevant error handling. Prefer small tests over broad tests that couple unrelated modules.
- Use synthetic data and deterministic fixtures. Do not use real supplier documents, customer data, credentials, or private pricing information.
- Use a nearby `conftest.py` only for fixtures shared by multiple tests in that scope; keep one-off fixtures in the test module.
- A test may live in a nearby package-level `tests/` directory when its behavior has no single owning implementation file or when a focused test suite spans multiple modules. Keep this exception narrow and name the file `<subject>_test.py`.
- Do not move existing tests as part of unrelated changes. New tests should follow the co-location rule.
