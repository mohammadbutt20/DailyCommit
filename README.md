# DailyCommit

Group coding practice that keeps everyone accountable. Everyone in a group gets the same problem each day, solves it in the browser with real, sandboxed code execution, and keeps one shared streak alive. The streak only continues if every member solves the day's problem.

Built as my individual technical capstone for Kappa Theta Pi (Alpha Beta chapter, Rutgers).

## The problem

Interview prep rewards consistent practice, but tools like LeetCode and NeetCode are built for one person. Skipping a day costs nothing, groups that want to prep together have no shared plan, and nothing keeps people practicing between assessments. DailyCommit turns daily practice into a group commitment that everyone can see.

## Features

- **Groups:** create a group, invite members with a code or link, and pick the group's timezone.
- **Daily problem:** every member gets the same problem each day, chosen automatically from problems the app can grade.
- **Group streak:** the streak grows only when every eligible member solves that day's problem.
- **In-browser editor:** solve in the Monaco editor (the editor behind VS Code) in Python, Java, or C++.
- **Live grading:** run the samples or submit, and watch each test's result arrive in real time.
- **Leaderboard and live activity:** see who solved and when, updated without refreshing.
- **Past problems and practice:** reopen any past daily problem and practice it without affecting the streak.
- **History and stats:** review your own submissions, the code you sent, and your solve stats.
- **Sign-in:** Discord login, plus a no-password dev login for local development.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Monaco editor, TanStack Query |
| Backend API | FastAPI (Python), SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Queue, live events, cache | Redis, arq |
| Code execution | Docker containers, one per run |
| Real-time | WebSockets with Redis pub/sub |
| Entry point | Caddy reverse proxy |
| Integrations | LeetCode (problem import), Discord (OAuth login) |
| Local setup | Docker Compose, WSL2 on Windows |

## How it works

A full diagram is in [docs/Daily Commit System Map.html](docs/Daily%20Commit%20System%20Map.html) (download it and open it in a browser).

1. **Caddy** is the single entry point. It routes `/api` and `/ws` to FastAPI and everything else to the Next.js app.
2. On submit, **FastAPI** saves the submission in **Postgres** and puts a job on a **Redis** queue. The API never runs user code.
3. A separate **worker** takes the job and starts a fresh, locked-down **Docker** container for the run. The container gets only the code and test inputs, never the expected answers.
4. The worker compares the output outside the container and publishes each result through Redis. FastAPI forwards it to the browser over a **WebSocket**, so results appear test by test.
5. On an accepted submission, the worker records the solve in Postgres.
6. A **scheduler** runs every few minutes. After midnight in each group's timezone, it scores the day, updates the streak, and assigns the next problem. It also recovers stuck submissions.

### The sandbox

Every submission is treated as hostile. Each run has:

- No network access
- An unprivileged user with all Linux capabilities dropped
- A read-only filesystem with a small private workspace
- Limits on memory, CPU, processes (64), output, and time
- No host files or secrets

Samples and hidden tests run in separate containers, so program output can never reveal hidden test inputs. Test timing is measured by the worker, not reported by the user's code.

### Problems and judge packs

Problem statements are imported from LeetCode and stored in the database; they are not committed to this repository. A problem can be solved in the editor only if it has a **judge pack** in `problems/leetcode/<slug>/`:

- `judge.yaml`: the function signature, how answers are compared, and time and memory limits
- `tests.json`: LeetCode's examples as sample tests, plus our own hidden edge-case tests
- Reference solutions in Python, Java, and C++

A judge pack loads only if every reference solution passes every test in the real sandbox. The repository also includes a few original problems in `problems/<slug>/`.

## Run it locally

**Requirements:** Docker and `make`. On Windows, use WSL2 with Docker Desktop's WSL integration turned on, and clone the repo inside the WSL filesystem.

```bash
git clone https://github.com/mohammadbutt20/DailyCommit.git
cd DailyCommit
make demo
```

`make demo` builds the sandbox images, starts the stack, runs database migrations, imports problems, validates every judge pack in the sandbox, and seeds a demo group. Then open **http://localhost:8080** and use dev login.

### Optional: Discord login

1. Create an application at https://discord.com/developers/applications.
2. Under **OAuth2 → Redirects**, add `http://localhost:8080/api/auth/discord/callback`.
3. Run `cp .env.example .env`, then set `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET`.
4. Run `make up`. The login page now shows **Continue with Discord**.

### Common commands

| Command | What it does |
|---|---|
| `make up` / `make down` | Start or stop the stack |
| `make logs s=worker` | Follow one service's logs |
| `make reset-db` | Delete all local data |
| `make test` | Backend and frontend unit tests |
| `make test-sandbox` | Adversarial tests against the real sandbox |
| `make validate-problems` | Run every reference solution in the sandbox |
| `make lint` | Ruff and TypeScript checks |
| `make help` | List every command |

## Testing

The project has backend unit and integration tests (including tests against a real Postgres), frontend tests, and an adversarial sandbox suite. The sandbox suite runs real attacks in Python, Java, and C++, including infinite loops, memory bombs, fork bombs, network access, disk filling, forged timing, and attempts to leak hidden test inputs. Every judge pack's reference solutions also run in the sandbox before a problem can load.

## Known limitations

- It runs locally and is not hosted yet.
- The set of problems that can be graded in the editor is still small.
- **Accepted** means passing this project's tests, not LeetCode's. A slower-than-intended solution may still pass.
- Containers share the host's kernel. A production deployment should add a stronger runtime such as gVisor.
- The LeetCode import uses an unofficial API that could change without notice.
- No load testing has been done yet.

## Future improvements

- Host it on Azure and run it with a real group
- Add more judge packs
- Live 1v1 VS mode with ELO ratings
- Runtime and memory stats on accepted submissions
- SM-2 spaced repetition to bring back problems you struggled with
- Discord reminders before a streak breaks
- Time and space complexity feedback

## More documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): design decisions, data model, and security details
- [CLAUDE.md](CLAUDE.md): conventions for working on the code
- [docs/](docs/): the project proposal and system map
