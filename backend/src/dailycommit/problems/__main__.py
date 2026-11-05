"""python -m dailycommit.problems {validate,sync} [--no-verify]

validate: check every problem folder (and, unless --no-verify, run reference solutions in the
          sandbox). Touches no database.
sync:     validate, then upsert into the database and retire problems no longer in the repo.

Verification needs the Docker socket, so run it in the worker container (make sync-problems).
"""

import argparse
import asyncio
import sys

from sqlalchemy import delete, select

from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.models import Problem, TestCase
from dailycommit.problems.loader import LoadedProblem, ProblemError, load_all
from dailycommit.sandbox.backend import DockerSandbox
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.sandbox.runner import TestInput, run_tests


def verify(problems: list[LoadedProblem]) -> list[str]:
    sandbox = DockerSandbox()
    failures = []
    for p in problems:
        tests = [TestInput(t.input, t.expected, t.sample) for t in p.tests]
        for lang_id, code in p.solutions.items():
            report = run_tests(
                sandbox,
                LANGUAGES[lang_id],
                code,
                p.spec.signature,
                tests,
                p.compare,
                p.spec.limits.model_dump(),
            )
            status = "ok" if report.verdict == "AC" else "FAIL"
            print(f"  {status} {p.spec.slug} [{lang_id}] {report.passed}/{report.total}")
            if report.verdict != "AC":
                bad = [r.ordinal for r in report.results if r.verdict != "AC"]
                failures.append(
                    f"{p.spec.slug} [{lang_id}]: {report.verdict} on tests {bad} {report.error or ''}"
                )
    return failures


async def sync(problems: list[LoadedProblem]) -> None:
    async with SessionLocal() as db, db.begin():
        existing = {p.slug: p for p in (await db.scalars(select(Problem))).all()}
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
            await db.execute(delete(TestCase).where(TestCase.problem_id == row.id))
            db.add_all(
                TestCase(
                    problem_id=row.id,
                    ordinal=i,
                    is_sample=t.sample,
                    input=t.input,
                    expected=t.expected,
                )
                for i, t in enumerate(lp.tests)
            )
            print(f"  synced {spec.slug}")
        for row in existing.values():
            if not row.retired:
                row.retired = True
                print(f"  retired {row.slug}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m dailycommit.problems")
    parser.add_argument("command", choices=["validate", "sync"])
    parser.add_argument("--no-verify", action="store_true", help="skip reference solutions")
    args = parser.parse_args()

    try:
        problems = load_all(settings.problems_dir)
    except ProblemError as e:
        print(f"invalid problem: {e}", file=sys.stderr)
        return 1
    print(f"{len(problems)} problems valid")

    if not args.no_verify:
        failures = verify(problems)
        if failures:
            print("reference solutions failed:\n  " + "\n  ".join(failures), file=sys.stderr)
            return 1

    if args.command == "sync":
        asyncio.run(sync(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
