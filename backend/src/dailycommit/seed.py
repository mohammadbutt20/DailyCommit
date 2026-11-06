"""Demo data: `python -m dailycommit.seed` (after `make sync-problems`). Safe to re-run: it does
nothing if the demo group exists (`make reset-db && make demo` rebuilds it fresh).

"Pledge Class Demo" (invite DEMO2026): Alice (leader), Bob, Chen and Dana, with three weeks of
history planned by `demo_plan` (pure and deterministic, so tests can check it):

- A different judge-pack problem every day (a problem returns only after 20 days), today's
  being best-time-to-buy-and-sell-stock.
- Everyone solves almost every day, at their own times (Alice mornings, Chen at lunch, Bob in
  the evening, Dana late) and in their own languages; some days start with a wrong answer or
  a time limit. Those failed tries are real code with the results our judge gives them
  (seed_attempts.py, re-judged by the tests).
- Two broken days: Dana misses day -13, and Bob gives up on day -6 after two wrong answers.
  The real rollover computes the streaks from this: best 8, current 5.
- Bob also practises past problems and runs samples, so "My history" has some depth.
- Today, only Alice has solved (if her usual time has passed); log in as anyone else to solve
  it live.
"""

import asyncio
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from dailycommit.api.auth.sessions import user_for_identity
from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.domain import timeutil
from dailycommit.models import (
    Group,
    GroupDailyProblem,
    GroupDaySolve,
    GroupMember,
    Problem,
    Submission,
    SubmissionResult,
    utcnow,
)
from dailycommit.problems.loader import LoadedJudgePack, load_judge_packs
from dailycommit.seed_attempts import ATTEMPTS
from dailycommit.services.rollover import rollover_all

INVITE = "DEMO2026"
GROUP_NAME = "Pledge Class Demo"
NAMES = ["Alice", "Bob", "Chen", "Dana"]
DAYS_BACK = 21  # history: day -21 .. -1, then today
RNG_SEED = 2026

# One problem per day, oldest first; index i is day -(21 - i). The list has 20 problems, so
# day -1 repeats day -21's and today repeats day -20's: a problem never returns within 20 days.
ORDER = [
    "two-sum",
    "best-time-to-buy-and-sell-stock",
    "container-with-most-water",
    "climbing-stairs",
    "group-anagrams",
    "valid-parentheses",
    "trapping-rain-water",
    "binary-search",
    "product-of-array-except-self",
    "contains-duplicate",
    "longest-substring-without-repeating-characters",
    "majority-element",
    "3sum",
    "valid-palindrome",
    "coin-change",
    "search-in-rotated-sorted-array",
    "merge-intervals",
    "daily-temperatures",
    "minimum-window-substring",
    "valid-anagram",
]

# When each member usually solves (minutes after local midnight) and in which language.
PERSONAS = {
    "Alice": ("python", 7 * 60, 9 * 60 + 40),
    "Chen": ("java", 11 * 60 + 40, 13 * 60 + 45),
    "Bob": ("python", 18 * 60 + 20, 22 * 60 + 40),
    "Dana": ("cpp", 20 * 60 + 15, 23 * 60 + 20),
}
BOB_LANGUAGE = {14: "cpp", 9: "java", 4: "cpp", 17: "java"}  # days back where Bob switches
# Failed tries before that day's Accepted: days back -> [(member, attempt)].
TRIES = {
    20: [("Bob", "best_time_max_minus_min")],
    18: [("Alice", "climbing_stairs_off_by_one")],
    15: [("Dana", "trapping_rain_water_quadratic")],  # then solves it in C++
    13: [("Chen", "product_by_division")],
    12: [("Alice", "contains_duplicate_neighbours")],
    9: [("Bob", "three_sum_brute_force")],  # then solves it in Java
    6: [("Bob", "rotated_plain_binary_search"), ("Bob", "rotated_plain_binary_search")],
    2: [("Alice", "valid_anagram_sets")],
}
MISSED = {13: "Dana", 6: "Bob"}  # Bob tried on day -6 (above) but never got it
BOB_RUNS = {11, 4}  # days back where Bob runs the samples before submitting
# Bob practising past problems: (days back, problem, language, failed tries first).
BOB_PRACTICE = [
    (12, "trapping-rain-water", "python", []),
    (10, "climbing-stairs", "python", ["climbing_stairs_off_by_one"]),
    (7, "group-anagrams", "java", []),
    (3, "coin-change", "cpp", []),
    (1, "minimum-window-substring", "python", []),
]


@dataclass(frozen=True)
class PlannedSubmission:
    member: str
    slug: str
    language: str
    kind: str  # submit | run | practice
    verdict: str
    results: str  # one letter per test (seed_attempts.py)
    attempt: str | None  # name in ATTEMPTS, or None for the reference solution
    at: datetime  # UTC
    day: date  # the group-local day it was made on
    credits: bool  # an Accepted submit of that day's problem: counts toward the streak


@dataclass(frozen=True)
class DemoPlan:
    start: date  # the day the group was created and everyone joined
    days: list[tuple[date, str]]  # (day, problem slug), oldest first, today last
    submissions: list[PlannedSubmission]  # in time order


def problem_for(back: int) -> str:
    """The problem `back` days before today (0 = today)."""
    return ORDER[(DAYS_BACK - back) % len(ORDER)]


def demo_plan(
    today: date, tz: ZoneInfo, now: datetime, test_counts: dict[str, tuple[int, int]]
) -> DemoPlan:
    """The whole demo history. `test_counts`: slug -> (samples, total tests). Pure."""
    rng = random.Random(RNG_SEED)
    subs: list[PlannedSubmission] = []

    def at(day: date, minute: int) -> datetime:
        return timeutil.day_start(day, tz) + timedelta(minutes=minute, seconds=rng.randint(0, 59))

    def accepted(member, slug, language, kind, day, when, credits) -> None:
        samples, total = test_counts[slug]
        n = samples if kind == "run" else total
        subs.append(
            PlannedSubmission(member, slug, language, kind, "AC", "A" * n, None, when, day, credits)
        )

    def failed(member, name, kind, day, when) -> None:
        a = ATTEMPTS[name]
        subs.append(
            PlannedSubmission(
                member, a.slug, "python", kind, a.verdict, a.results, name, when, day, False
            )
        )

    days = []
    for back in range(DAYS_BACK, -1, -1):
        day = today - timedelta(days=back)
        slug = problem_for(back)
        days.append((day, slug))
        for member, (language, earliest, latest) in PERSONAS.items():
            if member == "Bob":
                language = BOB_LANGUAGE.get(back, language)
            minute = rng.randint(earliest, latest)
            tries = [name for who, name in TRIES.get(back, []) if who == member]
            gap = rng.randint(6, 25)
            start = minute - gap * (len(tries) + (member == "Bob" and back in BOB_RUNS))
            when = at(day, start)
            if back == 0 and member != "Alice":
                continue  # today: only Alice so far
            if back == 0 and when > now:
                continue  # her usual time hasn't come yet
            for name in tries:
                failed(member, name, "submit", day, when)
                when += timedelta(minutes=gap)
            if MISSED.get(back) == member:
                continue
            if member == "Bob" and back in BOB_RUNS:
                accepted(member, slug, language, "run", day, when, False)
                when += timedelta(minutes=gap)
            accepted(member, slug, language, "submit", day, when, True)

    for back, slug, language, tries in BOB_PRACTICE:
        day = today - timedelta(days=back)
        when = at(day, rng.randint(22 * 60 + 45, 23 * 60 + 35))
        for name in tries:
            failed("Bob", name, "practice", day, when)
            when += timedelta(minutes=rng.randint(4, 9))
        accepted("Bob", slug, language, "practice", day, when, False)

    subs.sort(key=lambda s: s.at)
    return DemoPlan(start=today - timedelta(days=DAYS_BACK + 1), days=days, submissions=subs)


def _test_counts(packs: dict[str, LoadedJudgePack]) -> dict[str, tuple[int, int]]:
    return {slug: (sum(t.sample for t in p.tests), len(p.tests)) for slug, p in packs.items()}


LETTERS = {"A": "AC", "W": "WA", "T": "TLE", "s": "skipped"}


async def seed() -> None:
    packs = {p.slug: p for p in load_judge_packs(settings.problems_dir)}
    missing = sorted(set(ORDER) - set(packs))
    if missing:
        raise SystemExit(f"judge packs missing from problems/leetcode: {missing}")

    async with SessionLocal() as db:
        if await db.scalar(select(Group.id).where(Group.invite_code == INVITE)):
            print("demo group already exists; nothing to do")
            return
        rows = {
            p.slug: p
            for p in (await db.scalars(select(Problem).where(Problem.slug.in_(ORDER)))).all()
        }
        not_ready = sorted(s for s in ORDER if s not in rows or not rows[s].judgeable)
        if not_ready:
            raise SystemExit(f"problems not loaded yet: {not_ready}; run `make sync-problems`")

        now = utcnow()
        tz_name = settings.day_timezone
        tz = ZoneInfo(tz_name)
        today = timeutil.local_day(now, tz)
        plan = demo_plan(today, tz, now, _test_counts(packs))
        created = timeutil.day_start(plan.start, tz) + timedelta(hours=19, minutes=12)

        users = {n: await user_for_identity(db, "dev", n.lower(), n) for n in NAMES}
        group = Group(
            name=GROUP_NAME,
            invite_code=INVITE,
            timezone=tz_name,
            created_by=users["Alice"].id,
            created_at=created,
            last_rolled_day=plan.start,  # the first day the rollover scores is day -21
        )
        db.add(group)
        await db.flush()
        for n, name in enumerate(NAMES):
            db.add(
                GroupMember(
                    group_id=group.id,
                    user_id=users[name].id,
                    role="leader" if name == "Alice" else "member",
                    joined_at=created + timedelta(minutes=4 * n),
                )
            )
        for day, slug in plan.days:
            db.add(GroupDailyProblem(group_id=group.id, day=day, problem_id=rows[slug].id))

        rng = random.Random(RNG_SEED + 1)
        for p in plan.submissions:
            pack = packs[p.slug]
            tests = sorted(pack.tests, key=lambda t: not t.sample)  # submit order: samples first
            attempt = ATTEMPTS[p.attempt] if p.attempt else None
            code = attempt.code if attempt else pack.solutions[p.language]
            times = [
                None if v in "Ts" else rng.randint(0, 4 if p.language != "java" else 9)
                for v in p.results
            ]
            sub = Submission(
                user_id=users[p.member].id,
                problem_id=rows[p.slug].id,
                group_id=group.id,
                language=p.language,
                kind=p.kind,
                code=code,
                status="done",
                verdict=p.verdict,
                passed=p.results.count("A"),
                total=len(p.results),
                runtime_ms=max((t for t in times if t is not None), default=None),
                created_at=p.at,
                finished_at=p.at + timedelta(seconds=rng.randint(1, 4)),
            )
            db.add(sub)
            await db.flush()
            for i, (letter, ms) in enumerate(zip(p.results, times, strict=True)):
                sample = tests[i].sample
                actual = None
                if sample and letter == "A":
                    actual = tests[i].expected
                elif sample and attempt and i in attempt.sample_outputs:
                    actual = attempt.sample_outputs[i]
                db.add(
                    SubmissionResult(
                        submission_id=sub.id,
                        ordinal=i,
                        verdict=LETTERS[letter],
                        time_ms=ms,
                        actual=actual,
                    )
                )
            if p.credits:
                db.add(
                    GroupDaySolve(
                        group_id=group.id,
                        day=p.day,
                        user_id=users[p.member].id,
                        submission_id=sub.id,
                        solved_at=sub.finished_at,
                    )
                )
        await db.commit()

        await rollover_all(db, now)  # the real streak evaluation, day -21 .. yesterday
        await db.refresh(group)
        print(
            f"seeded {group.name!r} (invite {INVITE}) with {', '.join(NAMES)}: "
            f"{len(plan.days)} days, {len(plan.submissions)} submissions; "
            f"streak {group.current_streak}, best {group.best_streak}"
        )


if __name__ == "__main__":
    asyncio.run(seed())
