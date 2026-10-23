"""Problem files + Python harness + runner, end to end without Docker (LocalProcessSandbox)."""

import pytest

from dailycommit.problems.loader import load_all
from dailycommit.problems.schema import Signature, check_value
from dailycommit.sandbox.codegen.python import starter_code
from dailycommit.sandbox.languages import PYTHON
from dailycommit.sandbox.runner import HIDDEN_ERROR, TestInput, run_tests
from tests.conftest import PROBLEMS_DIR

PROBLEMS = load_all(PROBLEMS_DIR)
LIMITS = {"time_ms": 2000, "memory_mb": 128}
SIG = Signature.model_validate(
    {
        "function": "add",
        "params": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
        "returns": "int",
    }
)
TESTS = [TestInput({"a": 1, "b": 2}, 3, True), TestInput({"a": 5, "b": 5}, 10, False)]


def run(sandbox, code, tests=TESTS, limits=LIMITS, events=None):
    return run_tests(
        sandbox,
        PYTHON,
        code,
        SIG,
        tests,
        "exact",
        limits,
        events.append if events is not None else None,
    )


def test_repo_has_valid_problems():
    assert len(PROBLEMS) >= 5


@pytest.mark.parametrize("problem", PROBLEMS, ids=lambda p: p.spec.slug)
def test_reference_solution_passes(problem, local_sandbox):
    tests = [TestInput(t.input, t.expected, t.sample) for t in problem.tests]
    report = run_tests(
        local_sandbox,
        PYTHON,
        problem.solutions["python"],
        problem.spec.signature,
        tests,
        problem.compare,
        problem.spec.limits.model_dump(),
    )
    assert report.verdict == "AC", report


@pytest.mark.parametrize("problem", PROBLEMS, ids=lambda p: p.spec.slug)
def test_starter_code_runs_and_is_wrong(problem, local_sandbox):
    tests = [TestInput(t.input, t.expected, t.sample) for t in problem.tests]
    report = run_tests(
        local_sandbox,
        PYTHON,
        starter_code(problem.spec.signature),
        problem.spec.signature,
        tests,
        problem.compare,
        problem.spec.limits.model_dump(),
    )
    assert report.verdict == "WA"


def test_check_value_types():
    assert check_value("int[][]", [[1], []])
    assert not check_value("int", True)
    assert not check_value("int", 2**31)
    assert check_value("long", 2**31)
    assert check_value("double", 3)
    assert not check_value("string[]", ["a", 1])


def test_accepted_with_events(local_sandbox):
    events = []
    code = "class Solution:\n    def add(self, a, b):\n        print('debug', a)\n        return a + b\n"
    report = run(local_sandbox, code, events=events)
    assert (report.verdict, report.passed, report.total) == ("AC", 2, 2)
    assert [e["data"]["verdict"] for e in events] == ["AC", "AC"]
    # Samples reveal output and prints; hidden tests reveal neither.
    assert report.results[0].actual == 3 and "debug 1" in report.results[0].stdout
    assert report.results[1].actual is None and report.results[1].stdout is None


def test_wrong_answer(local_sandbox):
    report = run(local_sandbox, "class Solution:\n    def add(self, a, b):\n        return a - b\n")
    assert report.verdict == "WA"
    assert [r.verdict for r in report.results] == ["WA", "WA"]


def test_runtime_error_details_only_on_samples(local_sandbox):
    code = "class Solution:\n    def add(self, a, b):\n        raise ValueError(f'secret {a}')\n"
    report = run(local_sandbox, code)
    assert report.verdict == "RE"
    assert "secret 1" in report.results[0].error
    assert report.results[1].error == HIDDEN_ERROR


def test_syntax_error_is_compile_error(local_sandbox):
    report = run(local_sandbox, "class Solution:\n    def add(self, a, b)\n        return 1\n")
    assert report.verdict == "CE"
    assert "SyntaxError" in report.error


def test_missing_method(local_sandbox):
    report = run(local_sandbox, "class Solution:\n    def other(self):\n        pass\n")
    assert report.verdict == "RE"
    assert [r.verdict for r in report.results] == ["RE", "skipped"]


def test_non_serializable_return(local_sandbox):
    report = run(
        local_sandbox, "class Solution:\n    def add(self, a, b):\n        return {a, b}\n"
    )
    assert report.results[0].verdict == "RE"
    assert "JSON" in report.results[0].error


def test_slow_test_is_tle(local_sandbox):
    code = "import time\nclass Solution:\n    def add(self, a, b):\n        time.sleep(0.3)\n        return a + b\n"
    report = run(local_sandbox, code, limits={"time_ms": 100, "memory_mb": 128})
    assert report.verdict == "TLE"


def test_forged_result_lines_cannot_fake_accept(local_sandbox):
    # The marker is visible to user code, but expected outputs are not.
    code = (
        "import sys, json\n"
        "class Solution:\n"
        "    def add(self, a, b):\n"
        "        sys.__stdout__.write(sys.argv[1] + json.dumps({'i': 1, 'out': 0, 'ms': 0}) + '\\n')\n"
        "        sys.__stdout__.flush()\n"
        "        return a + b\n"
    )
    report = run(local_sandbox, code)
    assert report.results[1].verdict == "WA"
