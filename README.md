# DailyCommit

Group coding practice: everyone in a group gets the same problem each day, solves it in the browser (real, sandboxed code execution), and keeps a shared streak alive.

- Design and decisions: [ARCHITECTURE.md](ARCHITECTURE.md)
- Working on the code (people and Claude): [CLAUDE.md](CLAUDE.md)
- Product requirements: [docs/](docs/)

## Run it locally

Requires WSL2 + Docker Desktop on Windows (setup steps: ARCHITECTURE.md §12), or any Linux/macOS machine with Docker and `make`. Clone the repo inside the WSL filesystem, then:

```bash
make demo
```

That builds the sandbox images, starts the stack, applies migrations, imports LeetCode's Top Interview 150, loads the local problems and the judge packs in `problems/leetcode/` (running every reference solution in the sandbox), and seeds demo data. Imported problems with a judge pack (two-sum, valid-parentheses, merge-intervals so far) are the daily pool and are solved right here in the editor. Open **http://localhost:8080**.

Pick other LeetCode problems any time: `make import-leetcode LC="--plan leetcode-75"`, `LC="--difficulty medium --tag graph --limit 40"`, or `LC="two-sum https://leetcode.com/problems/lru-cache/"`.

### Sign in with Discord (optional)

Dev login works with no setup. To use real Discord accounts:

1. Create an application at https://discord.com/developers/applications.
2. Under **OAuth2 → Redirects**, add `http://localhost:8080/api/auth/discord/callback` (for another host, `<PUBLIC_URL>/api/auth/discord/callback`).
3. `cp .env.example .env` and set `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` from the OAuth2 page (and `PUBLIC_URL` if you're not on localhost:8080).
4. `make up`. The login page now shows **Continue with Discord**. Dev login stays available while `ENV=dev`.

## Demo script

1. **Log in** as **Bob** (dev login: no password). The seeded group "Pledge Class Demo" shows a 2-day streak (best 4) and the recent-days strip: Bob missed a day, which reset the streak. Alice has already solved today's problem.
2. **Open today's problem** → **Solve**. Write a wrong answer and click **Run samples**: per-test verdicts stream in live, and the failing example shows input / expected / output.
3. **Submit**: the daily problem is a LeetCode problem with a judge pack, so the page shows LeetCode's statement next to the editor. Submit in Python, Java or C++ (reference solutions are in `problems/leetcode/<slug>/solutions/`, or `problems/<slug>/solutions/` for local problems); tests turn green one by one, then *Accepted*. A LeetCode problem without a pack (a leader can pick any LeetCode URL) shows **Solve on LeetCode** instead: link your LeetCode account in the side panel (paste the code it gives you into your LeetCode profile Summary, then Verify), get *Accepted* on leetcode.com and click **I solved it, check now**, or wait a few minutes for the automatic check.
4. Open a second browser window (private mode) and log in as **Chen** on the group page: Bob's solve appears in the live activity feed, the member checklist and the leaderboard update without a refresh.
5. **Sandbox:** submit `while True: pass` (TLE), a memory bomb such as `x = [0] * 10**9` (MLE), or `import socket; socket.create_connection(("1.1.1.1", 80))` (RE, no network). `make test-sandbox` runs the full adversarial suite.
6. **History:** on the group page, **Past problems** lists every daily problem with who solved it; open one to practice it in the editor (practice never touches the streak). The header's **My history** shows your submissions (open one to see your code) and your stats.
7. **Groups:** create a new group, copy its invite link, and open it as another user to join. As leader (Alice), pause a member or pick tomorrow's problem.
8. **Streak rollover:** the scheduler evaluates each group's day at midnight in that group's timezone (picked when the group is created; `DAY_TIMEZONE` is the default) and assigns the next problem.

## Commands

`make help` lists all targets. The common ones: `make up`, `make down`, `make logs s=worker`, `make test`, `make test-sandbox`, `make lint`, `make reset-db`.
