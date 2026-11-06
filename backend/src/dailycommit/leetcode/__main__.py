"""python -m dailycommit.leetcode import [--plan SLUG ...] [--difficulty D] [--tag T ...]
                                     [--search TEXT] [--limit N] [SLUG_OR_URL ...]

Imports LeetCode questions as daily problems. Examples:

  import --plan top-interview-150            LeetCode's Top Interview 150 study plan
  import --plan leetcode-75 --plan top-sql-50
  import --difficulty medium --tag graph --limit 40
  import two-sum https://leetcode.com/problems/valid-parentheses/

Re-running is safe: unchanged questions are skipped, changed ones updated.
"""

import argparse
import asyncio
import sys

from dailycommit.db import SessionLocal
from dailycommit.leetcode import client as lc
from dailycommit.leetcode.importer import import_slugs


async def run(args: argparse.Namespace) -> int:
    slugs: list[str] = []
    for value in args.slugs:
        slug = lc.parse_slug(value)
        if slug is None:
            print(f"not a LeetCode problem slug or URL: {value!r}", file=sys.stderr)
            return 2
        slugs.append(slug)

    async with lc.new_client() as http:
        try:
            for plan in args.plan:
                name, plan_slugs = await lc.study_plan(http, plan)
                print(f"study plan {name!r}: {len(plan_slugs)} free questions")
                slugs += plan_slugs
            if args.difficulty or args.tag or args.search:
                found = await lc.list_slugs(
                    http,
                    difficulty=args.difficulty,
                    tags=args.tag,
                    search=args.search,
                    limit=args.limit,
                )
                print(f"problem list filter: {len(found)} free questions")
                slugs += found
            if not slugs:
                print("nothing to import: give --plan, a filter, or slugs", file=sys.stderr)
                return 2
            async with SessionLocal() as db, db.begin():
                result = await import_slugs(db, http, slugs)
        except lc.LeetCodeError as e:
            print(f"LeetCode: {e}", file=sys.stderr)
            return 1

    print(
        f"added {len(result.added)}, updated {len(result.updated)}, "
        f"unchanged {len(result.unchanged)}, skipped {len(result.skipped)}"
    )
    for slug, reason in result.skipped.items():
        print(f"  skipped {slug}: {reason}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m dailycommit.leetcode")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="import LeetCode questions as daily problems")
    imp.add_argument("slugs", nargs="*", help="problem slugs or leetcode.com problem URLs")
    imp.add_argument("--plan", action="append", default=[], help="study plan slug")
    imp.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    imp.add_argument("--tag", action="append", default=[], help="topic tag slug, e.g. graph")
    imp.add_argument("--search", help="keyword search in LeetCode's problem list")
    imp.add_argument("--limit", type=int, default=50, help="max questions from a filter")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
