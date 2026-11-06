"""python -m dailycommit.problems {validate,sync} [--no-verify]

validate: check every local problem and judge pack (and, unless --no-verify, run every
          reference solution in the sandbox). Touches no database.
sync:     validate, then upsert local problems, retire ones no longer in the repo, and attach
          judge packs to their imported LeetCode problems (importing any that are missing).
          Judge packs only load after their reference solutions pass, so --no-verify skips them.

Verification needs the Docker socket, so run it in the worker container (make sync-problems).
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy import delete, null, select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.leetcode import client as lc
from dailycommit.leetcode.importer import ensure_leetcode_problem
from dailycommit.models import Problem, TestCase
from dailycommit.problems.loader import (
    LoadedJudgePack,
    LoadedProblem,
    ProblemError,
    load_all,
    load_judge_packs,
)
from dailycommit.problems.schema import TestSpec
from dailycommit.sandbox.backend import DockerSandbox, SandboxBackend
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.sandbox.runner import TestInput, run_tests


def verify(
    problems: Sequence[LoadedProblem | LoadedJudgePack], sandbox: SandboxBackend | None = None
) -> list[str]:
    """Run every reference solution against every test; return the failures."""
    sandbox = sandbox or DockerSandbox()
    failures = []
    for p in problems:
        tests = [TestInput(t.input, t.expected, t.sample) for t in p.tests]
        for lang_id, code in p.solutions.items():
            report = run_tests(
                sandbox,
                LANGUAGES[lang_id],
                code,
                p.signature,
                tests,
                p.compare,
                p.limits.model_dump(),
                reveal_output=True,  # trusted reference code: show why it failed
            )
            status = "ok" if report.verdict == "AC" else "FAIL"
            print(f"  {status} {p.slug} [{lang_id}] {report.passed}/{report.total}")
            if report.verdict != "AC":
                bad = [r.ordinal for r in report.results if r.verdict != "AC"]
                failures.append(
                    f"{p.slug} [{lang_id}]: {report.verdict} on tests {bad} {report.error or ''}"
                )
    return failures


async def _replace_tests(db: AsyncSession, problem_id: int, tests: list[TestSpec]) -> None:
    await db.execute(delete(TestCase).where(TestCase.problem_id == problem_id))
    db.add_all(
        TestCase(
            problem_id=problem_id,
            ordinal=i,
            is_sample=t.sample,
            input=t.input,
            expected=t.expected,
        )
        for i, t in enumerate(tests)
    )


async def sync(problems: list[LoadedProblem]) -> None:
    async with SessionLocal() as db, db.begin():
        # Only local problems mirror problems/<slug>/; imported LeetCode ones are managed by
        # the importer (and their judge fields by sync_judge_packs).
        local = select(Problem).where(Problem.source == "local")
        existing = {p.slug: p for p in (await db.scalars(local)).all()}
        for lp in problems:
            spec = lp.spec
            row = existing.pop(spec.slug, None)
            if row and row.content_hash == lp.content_hash and not row.retired:
                continue
            if row is None:
                row = Problem(slug=spec.slug)
                db.add(row)
            row.title = spec.title
            row.difficulty = spec.difficulty
            row.topics = spec.topics
            row.statement_md = lp.statement_md
            row.signature = spec.signature.model_dump()
            row.compare = lp.compare
            row.limits = spec.limits.model_dump()
            row.content_hash = lp.content_hash
            row.retired = False
            await db.flush()
            await _replace_tests(db, row.id, lp.tests)
            print(f"  synced {spec.slug}")
        for row in existing.values():
            if not row.retired:
                row.retired = True
                print(f"  retired {row.slug}")


async def sync_judge_packs(packs: list[LoadedJudgePack]) -> list[str]:
    """Attach each (already verified) pack to its LeetCode problem, importing the problem if
    it isn't in the database yet, and detach packs removed from the repo. Returns errors."""
    errors: list[str] = []
    async with SessionLocal() as db, db.begin():
        judged = select(Problem).where(
            Problem.source == "leetcode", Problem.judge_hash.is_not(None)
        )
        stale = {p.slug: p for p in (await db.scalars(judged)).all()}
        async with lc.new_client() as http:
            for pack in packs:
                stale.pop(pack.slug, None)
                row = await db.scalar(select(Problem).where(Problem.slug == pack.slug))
                if row is None:
                    try:
                        row = await ensure_leetcode_problem(db, http, pack.slug)
                    except lc.LeetCodeError as e:
                        errors.append(f"{pack.slug}: couldn't import from LeetCode: {e}")
                        continue
                    if row is None:
                        errors.append(f"{pack.slug}: not a free LeetCode problem")
                        continue
                    print(f"  imported {pack.slug} from LeetCode")
                if row.source != "leetcode":
                    errors.append(f"{pack.slug}: slug belongs to a local problem")
                    continue
                if row.judge_hash == pack.judge_hash:
                    continue
                row.signature = pack.signature.model_dump()
                row.compare = pack.compare
                row.limits = pack.limits.model_dump()
                row.judge_hash = pack.judge_hash
                await db.flush()
                await _replace_tests(db, row.id, pack.tests)
                print(f"  judge pack loaded: {pack.slug}")
        for row in stale.values():
            # Back to a LeetCode-only problem: solved (and verified) on leetcode.com.
            # SQL NULL, not JSON 'null' (what a plain None becomes in a JSONB column).
            row.signature = row.compare = row.limits = null()
            row.judge_hash = None
            await db.execute(delete(TestCase).where(TestCase.problem_id == row.id))
            print(f"  judge pack removed: {row.slug}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m dailycommit.problems")
    parser.add_argument("command", choices=["validate", "sync"])
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip reference solutions (judge packs are then not loaded)",
    )
    args = parser.parse_args()

    try:
        problems = load_all(settings.problems_dir)
        packs = load_judge_packs(settings.problems_dir, {p.slug for p in problems})
    except ProblemError as e:
        print(f"invalid problem: {e}", file=sys.stderr)
        return 1
    print(f"{len(problems)} problems and {len(packs)} judge packs valid")

    if not args.no_verify:
        failures = verify([*problems, *packs])
        if failures:
            print("reference solutions failed:\n  " + "\n  ".join(failures), file=sys.stderr)
            return 1

    if args.command == "sync":
        return asyncio.run(sync_all(problems, packs, load_packs=not args.no_verify))
    return 0


async def sync_all(
    problems: list[LoadedProblem], packs: list[LoadedJudgePack], *, load_packs: bool
) -> int:
    await sync(problems)
    if not load_packs:
        if packs:
            print(f"--no-verify: skipped {len(packs)} judge packs (they need verification)")
        return 0
    errors = await sync_judge_packs(packs)
    if errors:
        print("judge packs not loaded:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
