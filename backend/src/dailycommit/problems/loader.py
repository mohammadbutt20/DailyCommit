"""Reading and validating problems/ folders. No database access.

Two formats:
- local problems, problems/<slug>/: original content with its own statement.
- judge packs, problems/leetcode/<slug>/: how to judge an imported LeetCode problem in our
  sandbox. The statement (and title, difficulty, topics) comes from the LeetCode import and is
  never committed, so a pack has no statement.md.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dailycommit.problems.schema import (
    JudgePackSpec,
    Limits,
    ProblemSpec,
    Signature,
    TestSpec,
    check_value,
    compare_json,
)
from dailycommit.sandbox.languages import LANGUAGES

JUDGE_PACKS_DIR = "leetcode"  # under problems/


class ProblemError(Exception):
    pass


@dataclass
class LoadedProblem:
    spec: ProblemSpec
    statement_md: str
    tests: list[TestSpec]
    solutions: dict[str, str]  # language id -> reference solution source
    content_hash: str

    @property
    def slug(self) -> str:
        return self.spec.slug

    @property
    def signature(self) -> Signature:
        return self.spec.signature

    @property
    def limits(self) -> Limits:
        return self.spec.limits

    @property
    def compare(self) -> Any:
        return compare_json(self.spec.compare)


@dataclass
class LoadedJudgePack:
    spec: JudgePackSpec
    tests: list[TestSpec]
    solutions: dict[str, str]
    judge_hash: str  # over judge.yaml, tests.json and every reference solution

    @property
    def slug(self) -> str:
        return self.spec.slug

    @property
    def signature(self) -> Signature:
        return self.spec.signature

    @property
    def limits(self) -> Limits:
        return self.spec.limits

    @property
    def compare(self) -> Any:
        return compare_json(self.spec.compare)


def _read(path: Path, name: str) -> bytes:
    f = path / name
    if not f.is_file():
        raise ProblemError(f"{path.name}: missing {name}")
    return f.read_bytes()


def _solutions(path: Path) -> dict[str, str]:
    solutions = {}
    for lang in LANGUAGES.values():
        ref = path / "solutions" / f"ref{lang.extension}"
        if ref.is_file():
            solutions[lang.id] = ref.read_text()
    return solutions


def _tests(path: Path, raw: bytes) -> list[TestSpec]:
    try:
        return [TestSpec.model_validate(t) for t in json.loads(raw)]
    except (ValidationError, ValueError) as e:
        raise ProblemError(f"{path.name}: tests.json: {e}") from e


def load_problem(path: Path) -> LoadedProblem:
    raw_spec, raw_statement, raw_tests = (
        _read(path, "problem.yaml"),
        _read(path, "statement.md"),
        _read(path, "tests.json"),
    )
    try:
        spec = ProblemSpec.model_validate(yaml.safe_load(raw_spec))
    except (ValidationError, ValueError, yaml.YAMLError) as e:
        raise ProblemError(f"{path.name}: {e}") from e
    tests = _tests(path, raw_tests)
    if spec.slug != path.name:
        raise ProblemError(f"{path.name}: slug {spec.slug!r} must match the folder name")

    problem = LoadedProblem(
        spec=spec,
        statement_md=raw_statement.decode(),
        tests=tests,
        solutions=_solutions(path),
        content_hash=hashlib.sha256(raw_spec + raw_statement + raw_tests).hexdigest(),
    )
    errors = validate_tests(problem.signature, problem.tests, problem.solutions)
    if errors:
        raise ProblemError(f"{path.name}: " + "; ".join(errors))
    return problem


def load_judge_pack(path: Path) -> LoadedJudgePack:
    if (path / "statement.md").exists():
        raise ProblemError(
            f"leetcode/{path.name}: judge packs must not contain statement.md "
            "(the statement comes from the LeetCode import)"
        )
    raw_spec, raw_tests = _read(path, "judge.yaml"), _read(path, "tests.json")
    try:
        spec = JudgePackSpec.model_validate(yaml.safe_load(raw_spec))
    except (ValidationError, ValueError, yaml.YAMLError) as e:
        raise ProblemError(f"leetcode/{path.name}: {e}") from e
    tests = _tests(path, raw_tests)
    if spec.slug != path.name:
        raise ProblemError(f"leetcode/{path.name}: slug {spec.slug!r} must match the folder name")

    solutions = _solutions(path)
    digest = hashlib.sha256(raw_spec + b"\x1f" + raw_tests)
    for lang_id in sorted(solutions):
        digest.update(b"\x1f" + lang_id.encode() + b"\x1f" + solutions[lang_id].encode())
    pack = LoadedJudgePack(
        spec=spec, tests=tests, solutions=solutions, judge_hash=digest.hexdigest()
    )
    errors = validate_tests(pack.signature, pack.tests, pack.solutions)
    missing = sorted(set(LANGUAGES) - set(solutions))
    if missing:
        errors.append(f"needs a reference solution in every language; missing {missing}")
    if errors:
        raise ProblemError(f"leetcode/{path.name}: " + "; ".join(errors))
    return pack


def validate_tests(
    signature: Signature, tests: list[TestSpec], solutions: dict[str, str]
) -> list[str]:
    errors: list[str] = []
    names = [param.name for param in signature.params]
    if not any(t.sample for t in tests):
        errors.append("needs at least one sample test")
    if not any(not t.sample for t in tests):
        errors.append("needs at least one hidden test")
    if not solutions:
        errors.append("needs a reference solution in solutions/")
    for n, t in enumerate(tests):
        if sorted(t.input) != sorted(names):
            errors.append(f"test {n}: input keys {sorted(t.input)} != params {sorted(names)}")
            continue
        for param in signature.params:
            if not check_value(param.type, t.input[param.name]):
                errors.append(f"test {n}: {param.name} is not a valid {param.type}")
        if not check_value(signature.returns, t.expected):
            errors.append(f"test {n}: expected is not a valid {signature.returns}")
    return errors


def load_all(root: Path) -> list[LoadedProblem]:
    """The local problems (every folder in problems/ except the judge packs' leetcode/)."""
    if not root.is_dir():
        raise ProblemError(f"problems directory {root} not found")
    return [
        load_problem(d) for d in sorted(root.iterdir()) if d.is_dir() and d.name != JUDGE_PACKS_DIR
    ]


def load_judge_packs(root: Path, local_slugs: set[str] | None = None) -> list[LoadedJudgePack]:
    """Every judge pack in problems/leetcode/. `local_slugs` (if given) are checked for
    collisions: a slug names one problem row, either local or LeetCode."""
    packs_dir = root / JUDGE_PACKS_DIR
    if not packs_dir.is_dir():
        return []
    packs = [load_judge_pack(d) for d in sorted(packs_dir.iterdir()) if d.is_dir()]
    clash = sorted({p.slug for p in packs} & (local_slugs or set()))
    if clash:
        raise ProblemError(f"judge pack slugs also used by local problems: {clash}")
    return packs
