"""A member's personal stats, from their submissions.

- Judged: a `submit` or `practice` that finished with a real verdict. Samples-only `run`s
  and internal errors (IE, our fault) don't count either way.
- Accepted rate: accepted / judged.
- Problems solved: distinct problems with an accepted submit or practice. Solving the same
  problem twice, or in two languages, counts once (per language once in `by_language`).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

JUDGED_KINDS = frozenset({"submit", "practice"})


@dataclass(frozen=True)
class SubmissionFact:
    problem_id: int
    kind: str  # run | submit | practice
    status: str  # queued | running | done
    verdict: str | None
    language: str
    difficulty: str  # of the problem


@dataclass(frozen=True)
class Stats:
    problems_solved: int
    submissions: int
    accepted: int
    accepted_rate: float | None  # None until there's a judged submission
    by_language: dict[str, int] = field(default_factory=dict)
    by_difficulty: dict[str, int] = field(default_factory=dict)


def judged(f: SubmissionFact) -> bool:
    return f.kind in JUDGED_KINDS and f.status == "done" and f.verdict not in (None, "IE")


def compute(facts: Iterable[SubmissionFact]) -> Stats:
    counted = [f for f in facts if judged(f)]
    accepted = [f for f in counted if f.verdict == "AC"]
    solved = {f.problem_id: f.difficulty for f in accepted}
    per_language: dict[str, set[int]] = {}
    for f in accepted:
        per_language.setdefault(f.language, set()).add(f.problem_id)
    per_difficulty: dict[str, int] = {}
    for difficulty in solved.values():
        per_difficulty[difficulty] = per_difficulty.get(difficulty, 0) + 1
    return Stats(
        problems_solved=len(solved),
        submissions=len(counted),
        accepted=len(accepted),
        accepted_rate=len(accepted) / len(counted) if counted else None,
        by_language={lang: len(ids) for lang, ids in sorted(per_language.items())},
        by_difficulty=dict(sorted(per_difficulty.items())),
    )
