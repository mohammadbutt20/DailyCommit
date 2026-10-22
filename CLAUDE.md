# CLAUDE.md

Daily Commit: a group coding-practice platform. Members solve a shared daily problem (Python/Java/C++) in a browser editor with sandboxed execution, keep a group streak alive, and compete on leaderboards. Current focus: the **P0 midpoint demo**, built as scaffolding for P1 (VS mode/ELO, SM-2, mock interviews, peer review, analytics, Discord bot).

**Read [ARCHITECTURE.md](ARCHITECTURE.md) before making structural changes.** It records every settled decision and why. If a change contradicts it, update ARCHITECTURE.md in the same change, or raise it with the user first.

## Stack
Next.js (App Router) + TypeScript + Tailwind + Monaco + TanStack Query · FastAPI (Python 3.12, uv) · SQLAlchemy 2 async + Alembic · PostgreSQL · Redis + arq (queue, cron, pub/sub) · Docker sandbox per submission · Caddy as single origin · Docker Compose.

## Repo map
- `web/`: Next.js app. `web/src/lib/api/schema.ts` is **generated**; never hand-edit it.
- `backend/src/dailycommit/`: one Python package with three entrypoints: `api/` (FastAPI), `jobs/worker.py` (executes submissions), `jobs/scheduler.py` (daily rollover cron).
  - `domain/`: pure business logic (streaks, daily pick, leaderboard, time math; later SM-2, ELO).
  - `sandbox/`: Docker orchestration, harness/starter-code generation, output comparison.
  - `problems/`: CLI that validates and syncs `problems/` into the DB.
- `sandbox/images/`: per-language sandbox Dockerfiles.
- `problems/<slug>/`: `problem.yaml`, `statement.md`, `tests.json`, `solutions/ref.*`.
- `infra/`: `compose.yaml` (dev), `compose.prod.yaml`, `Caddyfile`.
- `docs/`: PRD and system map (historical; ARCHITECTURE.md supersedes them where they differ).

## Commands
Run everything from **inside WSL** (Ubuntu), in the repo at `~/dev/DailyCommit`, not from PowerShell or `/mnt/c`.

```bash
make up               # start the whole stack (http://localhost:8080)
make down
make sandbox-images   # build python/java/cpp sandbox images
make migrate          # alembic upgrade head
make sync-problems    # validate + load problems/ (runs reference solutions in the sandbox)
make seed             # demo users/group/history; use dev login to sign in
make test             # backend unit + API tests
make test-sandbox     # adversarial sandbox suite (needs Docker)
make gen-api          # regenerate web/src/lib/api/schema.ts from FastAPI OpenAPI
```

## Invariants (do not break)
1. **The API and worker never execute user code in-process.** User code runs only inside a sandbox container with the limits in ARCHITECTURE.md §5. Never loosen those flags (network, caps, read-only, pids, memory, user) without explicit approval.
2. **Expected outputs never enter the sandbox,** and hidden tests never reach the browser. Comparison happens in the worker.
3. **`domain/` is pure:** no DB, Redis, HTTP or clock access (pass `now`/dates in). Every rule there has unit tests.
4. **All "what day is it" math goes through `domain/timeutil.py`** using the group's IANA timezone. Never use server-local dates or naive datetimes; store UTC `timestamptz`.
5. **Scheduled jobs are idempotent.** They're backed by unique constraints and safe to re-run or run late. Exactly one `scheduler` replica.
6. **Schema changes only via Alembic migrations.**
7. **After changing API routes or schemas, run `make gen-api`** and fix the TypeScript errors it surfaces.
8. **Dev login exists only when `ENV=dev`.** The route must not be registered otherwise.
9. Only `submit` (not `run`) submissions with verdict `AC` count toward streaks and leaderboards.

## Conventions
- **Python:** uv for deps, ruff for lint/format, type hints everywhere, async SQLAlchemy sessions via FastAPI dependencies, Pydantic models in `schemas/` (don't return ORM objects), settings only via `config.py`.
- **TypeScript:** `strict` mode, use the generated API types (no hand-written duplicates), server state through TanStack Query, live updates through the shared `useTopic` WebSocket hook.
- **Problems:** original content only (no copying LeetCode/NeetCode). Every problem ships a reference solution and hand-written edge-case tests.
- **Scope:** finish P0 end to end before starting P1. P1 features plug in at the extension points in ARCHITECTURE.md §11.
- Keep the README's demo script up to date when the setup or demo flow changes.
