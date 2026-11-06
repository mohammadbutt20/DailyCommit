# CLAUDE.md

Daily Commit: a group coding-practice platform. Members solve a shared daily problem (Python/Java/C++) in a browser editor with sandboxed execution, keep a group streak alive, and compete on leaderboards. Current focus: the **P0 midpoint demo**, built as scaffolding for P1 (VS mode/ELO, SM-2, mock interviews, peer review, analytics, Discord bot).

**Current state:** P0 slices 0–3 and 6 are built: Python/Java/C++ sandbox, Discord OAuth + dev login, per-group timezones, LeetCode import with judge packs (imported problems solved and graded here). Next slices (VPS, load test) are listed in ARCHITECTURE.md §15; build each as its own change.

**Read [ARCHITECTURE.md](ARCHITECTURE.md) before making structural changes.** It records every settled decision and why. If a change contradicts it, update ARCHITECTURE.md in the same change, or raise it with the user first.

## Stack
Next.js (App Router) + TypeScript + Tailwind + Monaco + TanStack Query · FastAPI (Python 3.12, uv) · SQLAlchemy 2 async + Alembic · PostgreSQL · Redis + arq (queue, cron, pub/sub) · Docker sandbox per submission · Caddy as single origin · Docker Compose.

## Repo map
- `web/`: Next.js app. `web/src/lib/api/schema.ts` is **generated**; never hand-edit it.
- `backend/src/dailycommit/`: one Python package with three entrypoints: `api/` (FastAPI), `jobs/worker.py` (executes submissions), `jobs/scheduler.py` (daily rollover cron).
  - `domain/`: pure business logic (streaks, daily pick, leaderboard, activity feed, time math; later SM-2, ELO).
  - `services/`: DB/Redis operations shared by the three entrypoints (rollover, solves, leaderboard cache, events). `services/clock.py` is the only place that decides a group's timezone.
  - `sandbox/`: Docker orchestration, language registry, harness/starter-code generation, output comparison.
  - `problems/`: CLI that validates and syncs `problems/` into the DB.
  - `leetcode/`: LeetCode GraphQL client (the only code that talks to LeetCode) and the import CLI.
- `sandbox/images/`: per-language sandbox Dockerfiles.
- `problems/<slug>/`: local (original) problems: `problem.yaml`, `statement.md`, `tests.json`, `solutions/ref.*`.
- `problems/leetcode/<slug>/`: judge packs for imported LeetCode problems: `judge.yaml`, `tests.json`, `solutions/ref.{py,java,cpp}`. No statement (it comes from the import).
- `infra/`: `compose.yaml` (dev), `compose.prod.yaml`, `Caddyfile`.
- `docs/`: PRD and system map (historical; ARCHITECTURE.md supersedes them where they differ).

## Commands
Run everything from **inside WSL** (Ubuntu), in the repo at `~/dev/DailyCommit`, not from PowerShell or `/mnt/c`.

```bash
make demo             # first run: sandbox images, stack, migrations, problems, seed data
make up               # start the whole stack (http://localhost:8080)
make down
make sandbox-images   # build the per-language sandbox images
make migrate          # alembic upgrade head
make validate-problems  # check problems/ + run reference solutions (no DB writes)
make sync-problems    # validate + load problems/ into the DB
make check-examples   # judge packs' samples == LeetCode's examples (reads imported statements)
make import-leetcode  # import LeetCode problems (default Top Interview 150; LC="--plan leetcode-75" etc.)
make seed             # demo users/group/history; use dev login to sign in
make test             # backend unit tests + web unit tests (node --test src/**/*.test.ts)
make test-sandbox     # adversarial sandbox suite (needs Docker + sandbox images)
make lint             # ruff + tsc
make gen-api          # regenerate web/src/lib/api/schema.ts from FastAPI OpenAPI
```

Backend unit tests also run without Docker: `cd backend && uv sync && uv run pytest`. They use a test-only `LocalProcessSandbox` (tests/conftest.py) that runs the real harness as a plain subprocess. Never use it outside tests.

## Invariants (do not break)
1. **The API and worker never execute user code in-process.** User code runs only inside a sandbox container with the limits in ARCHITECTURE.md §5. Never loosen those flags (network, caps, read-only, pids, memory, user) without explicit approval.
2. **Expected outputs never enter the sandbox,** and comparison happens in the worker. Hidden-test inputs do enter it, but only in a container whose program-controlled output (stdout, return values, error and compiler text) is never shown (`runner.judge_submission`); the API never returns hidden inputs. **Time is measured by the worker**, never trusted from harness lines (ARCHITECTURE.md §5).
3. **`domain/` is pure:** no DB, Redis, HTTP or clock access (pass `now`/dates in). Every rule there has unit tests.
4. **All "what day is it" math goes through `domain/timeutil.py`** using the group's IANA timezone. Never use server-local dates or naive datetimes; store UTC `timestamptz`.
5. **Scheduled jobs are idempotent.** They're backed by unique constraints and safe to re-run or run late. Exactly one `scheduler` replica.
6. **Schema changes only via Alembic migrations.**
7. **After changing API routes or schemas, run `make gen-api`** and fix the TypeScript errors it surfaces.
8. **Dev login exists only when `ENV=dev`.** The route must not be registered otherwise.
9. Only `submit` (not `run` or `practice`) submissions with verdict `AC` count toward streaks and leaderboards. `practice` (past problems) is judged on every test but never credited.

## Conventions
- **Python:** uv for deps, ruff for lint/format, type hints everywhere, async SQLAlchemy sessions via FastAPI dependencies, Pydantic models in `schemas/` (don't return ORM objects), settings only via `config.py`.
- **TypeScript:** `strict` mode, use the generated API types (no hand-written duplicates), server state through TanStack Query, live updates through the shared `useTopic` WebSocket hook.
- **Problems:** the daily pool is LeetCode problems imported with `make import-leetcode` that have a **judge pack** in `problems/leetcode/<slug>/`; members solve them in our editor and our sandbox grades them (ARCHITECTURE.md §6). Only judgeable problems are auto-picked. Never commit LeetCode statements (public repo); pack samples are LeetCode's examples, hidden tests are our own edge cases. Every pack ships `ref.py`, `ref.java` and `ref.cpp`, and they must all pass `make validate-problems`. Local `problems/` are for original content: each ships a reference solution and hand-written edge-case tests.
- **Scope:** finish P0 end to end before starting P1. P1 features plug in at the extension points in ARCHITECTURE.md §11.
- Keep the README's demo script up to date when the setup or demo flow changes.
