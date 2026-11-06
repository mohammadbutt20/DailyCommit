"""Judge packs (problems/leetcode/<slug>/): loading, validation, and reference solutions run
through the real harness without Docker. The Java/C++ references run in the real sandbox via
`make validate-problems` and the sandbox suite (test_sandbox_compiled.py)."""

import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from dailycommit.problems.__main__ import verify
from dailycommit.problems.loader import (
    JUDGE_PACKS_DIR,
    ProblemError,
    load_all,
    load_judge_pack,
    load_judge_packs,
)
from dailycommit.sandbox.codegen.python import starter_code
from dailycommit.sandbox.languages import LANGUAGES, PYTHON
from dailycommit.sandbox.runner import TestInput, run_tests
from tests.conftest import PROBLEMS_DIR

PACKS = load_judge_packs(PROBLEMS_DIR, {p.slug for p in load_all(PROBLEMS_DIR)})
PILOTS = {"two-sum", "valid-parentheses", "merge-intervals"}


def run(sandbox, pack, code):
    tests = [TestInput(t.input, t.expected, t.sample) for t in pack.tests]
    return run_tests(
        sandbox, PYTHON, code, pack.signature, tests, pack.compare, pack.limits.model_dump()
    )


def test_repo_has_the_pilot_packs():
    assert PILOTS <= {p.slug for p in PACKS}


def test_local_problems_exclude_the_judge_packs():
    assert all(p.slug not in PILOTS for p in load_all(PROBLEMS_DIR))


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.slug)
def test_pack_ships_every_language_and_no_statement(pack):
    assert set(pack.solutions) == set(LANGUAGES)
    assert not (PROBLEMS_DIR / JUDGE_PACKS_DIR / pack.slug / "statement.md").exists()


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.slug)
def test_reference_solution_passes(pack, local_sandbox):
    report = run(local_sandbox, pack, pack.solutions["python"])
    assert report.verdict == "AC", report


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.slug)
def test_starter_code_is_not_accepted(pack, local_sandbox):
    assert run(local_sandbox, pack, starter_code(pack.signature)).verdict == "WA"


def test_verify_reports_a_failing_reference(local_sandbox):
    pack = next(p for p in PACKS if p.slug == "two-sum")
    good = dataclasses.replace(pack, solutions={"python": pack.solutions["python"]})
    bad = dataclasses.replace(
        pack,
        solutions={
            "python": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n"
        },
    )
    assert verify([good], local_sandbox) == []
    [failure] = verify([bad], local_sandbox)
    assert failure.startswith("two-sum [python]: WA")


# --- validation, on a copy of a real pack -------------------------------------------------


@pytest.fixture
def pack_dir(tmp_path: Path) -> Path:
    """problems/ with a copy of the two-sum pack, ready to be broken."""
    shutil.copytree(
        PROBLEMS_DIR / JUDGE_PACKS_DIR / "two-sum", tmp_path / JUDGE_PACKS_DIR / "two-sum"
    )
    return tmp_path / JUDGE_PACKS_DIR / "two-sum"


def edit_tests(pack_dir: Path, fn) -> None:
    path = pack_dir / "tests.json"
    path.write_text(json.dumps(fn(json.loads(path.read_text()))))


def test_copy_loads(pack_dir):
    assert load_judge_pack(pack_dir).slug == "two-sum"


def test_statement_md_is_rejected(pack_dir):
    (pack_dir / "statement.md").write_text("copied from LeetCode")
    with pytest.raises(ProblemError, match="must not contain statement.md"):
        load_judge_pack(pack_dir)


@pytest.mark.parametrize("missing", ["ref.java", "ref.cpp", "ref.py"])
def test_every_language_is_required(pack_dir, missing):
    (pack_dir / "solutions" / missing).unlink()
    with pytest.raises(ProblemError, match="every language"):
        load_judge_pack(pack_dir)


def test_needs_a_sample_and_a_hidden_test(pack_dir):
    edit_tests(pack_dir, lambda ts: [t for t in ts if t["sample"]])
    with pytest.raises(ProblemError, match="hidden test"):
        load_judge_pack(pack_dir)
    shutil.copy(PROBLEMS_DIR / JUDGE_PACKS_DIR / "two-sum" / "tests.json", pack_dir)
    edit_tests(pack_dir, lambda ts: [t for t in ts if not t["sample"]])
    with pytest.raises(ProblemError, match="sample test"):
        load_judge_pack(pack_dir)


def test_tests_are_type_checked(pack_dir):
    edit_tests(pack_dir, lambda ts: [{**ts[0], "expected": "0,1"}, *ts[1:]])
    with pytest.raises(ProblemError, match="expected is not a valid int"):
        load_judge_pack(pack_dir)


def test_slug_must_match_folder(pack_dir):
    yaml_path = pack_dir / "judge.yaml"
    yaml_path.write_text(yaml_path.read_text().replace("slug: two-sum", "slug: two-summ"))
    with pytest.raises(ProblemError, match="must match the folder name"):
        load_judge_pack(pack_dir)


def test_slug_clash_with_a_local_problem(pack_dir):
    root = pack_dir.parents[1]
    with pytest.raises(ProblemError, match="also used by local problems"):
        load_judge_packs(root, {"two-sum"})


def test_judge_hash_covers_tests_and_solutions(pack_dir):
    before = load_judge_pack(pack_dir).judge_hash
    ref = pack_dir / "solutions" / "ref.cpp"
    ref.write_text(ref.read_text() + "\n")
    after_solution = load_judge_pack(pack_dir).judge_hash
    edit_tests(pack_dir, lambda ts: ts[:-1])
    after_tests = load_judge_pack(pack_dir).judge_hash
    assert len({before, after_solution, after_tests}) == 3


def test_no_leetcode_dir_means_no_packs(tmp_path):
    assert load_judge_packs(tmp_path) == []
