# Manual API checks

These requests are for manual use in VS Code; they are not an automated test suite and do not run in CI.

## Setup

1. From the repository root, follow the backend configuration steps in the main [README](../../../../README.md) to create `apps/backend/.env` and set `DATABASE_URL`.
2. Start the local database from the repository root:

   ```powershell
   docker compose up -d db
   ```

3. Start the API from `apps/backend`:

   ```powershell
   uv sync
   uv run uvicorn supplylens.api:app --reload
   ```

4. Install the VS Code **REST Client** extension and open [`health-check.http`](health-check.http).
5. Select **Send Request** above either request.

## Expected responses

- `GET /health` returns `200` with `{"status":"ok"}`. It checks that the API process responds and does not depend on the database.
- `GET /api/v1/health/ready` returns `200` with `{"status":"healthy"}` when PostgreSQL is reachable. It returns `503` when the database is unavailable.
