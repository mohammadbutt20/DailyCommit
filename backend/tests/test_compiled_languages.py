"""Java and C++: codegen and the runner's compile-step handling, without Docker. The real
compile-and-run behaviour is covered by test_sandbox_docker.py (make test-sandbox)."""

import json

import pytest

from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import RunOutcome, RunRequest
from dailycommit.sandbox.codegen import cpp, java
from dailycommit.sandbox.languages import COMPILE_FAILED, CPP, JAVA, LANGUAGES
from dailycommit.sandbox.runner import HIDDEN_ERROR, TestInput, run_tests

SIG = Signature.model_validate(
    {
        "function": "merge",
        "params": [{"name": "blocks", "type": "int[][]"}, {"name": "label", "type": "string"}],
        "returns": "long[]",
    }
)
LIMITS = {"time_ms": 1000, "memory_mb": 128}


@pytest.mark.parametrize(
    ("t", "j", "c"),
    [
        ("int", "int", "int"),
        ("long", "long", "long long"),
        ("double[]", "double[]", "vector<double>"),
        ("bool[][]", "boolean[][]", "vector<vector<bool>>"),
        ("string[]", "String[]", "vector<string>"),
    ],
)
def test_type_mapping(t, j, c):
    assert java.java_type(t) == j
    assert cpp.cpp_type(t) == c


def test_java_starter_code_compiles_shape():
    code = java.starter_code(SIG)
    assert "public long[] merge(int[][] blocks, String label)" in code
    assert "return new long[0];" in code  # compiles and runs (WA), unlike an empty body


def test_cpp_starter_code_shape():
    code = cpp.starter_code(SIG)
    assert "vector<long long> merge(vector<vector<int>>& blocks, string label)" in code
    assert "return {};" in code


def test_harnesses_read_every_param_by_name():
    jh, ch = java.harness(SIG), cpp.harness(SIG)
    assert 'GSON.fromJson(c.get("blocks"), int[][].class)' in jh
    assert 'GSON.fromJson(c.get("label"), String.class)' in jh
    assert "new Solution().merge(a0, a1)" in jh
    assert 'dcio::get<vector<vector<int>>>(i, "blocks")' in ch
    assert "vector<long long> r = sol.merge(a0, a1)" in ch


@pytest.mark.parametrize("lang", [JAVA, CPP])
def test_compile_wrapper_passes_marker_as_argument(lang):
    argv = lang.run_command("@@m@@", 128)
    assert argv[:2] == ["sh", "-c"] and argv[-1] == "@@m@@"
    assert "@@m@@" not in argv[2]  # never interpolated into the script
    assert COMPILE_FAILED in argv[2]


def test_java_heap_follows_problem_limit():
    assert "-Xmx256m" in JAVA.run_command("@@m@@", 256)[2]


def test_registry():
    assert set(LANGUAGES) == {"python", "java", "cpp"}


class ScriptedSandbox:
    """Replays harness output lines (with the run's marker) and a final outcome."""

    def __init__(self, lines: list[dict | str], outcome: RunOutcome) -> None:
        self.lines, self.outcome = lines, outcome
        self.request: RunRequest | None = None

    def run(self, req: RunRequest, on_line) -> RunOutcome:
        self.request = req
        mark = req.argv[-1]
        for line in self.lines:
            on_line(mark + (line if isinstance(line, str) else json.dumps(line)))
        return self.outcome


TESTS = [
    TestInput({"blocks": [], "label": "a"}, [], True),
    TestInput({"blocks": [], "label": "b"}, [], False),
]


def run(sandbox, lang=CPP):
    return run_tests(sandbox, lang, "code", SIG, TESTS, "exact", LIMITS)


def test_compile_failure_reports_compiler_output():
    sandbox = ScriptedSandbox(
        [COMPILE_FAILED],
        RunOutcome(exit_code=1, stderr="solution.cpp:3:5: error: expected ';'\n"),
    )
    report = run(sandbox)
    assert report.verdict == "CE"
    assert "solution.cpp:3:5" in report.error
    assert report.results == []


def test_compile_marker_after_results_is_ignored():
    # Only the wrapper prints it before any user code runs; a late one is user forgery.
    lines = [
        {"i": 0, "out": [], "ms": 1, "err": None, "stdout": ""},
        COMPILE_FAILED,
        {"i": 1, "out": [], "ms": 1, "err": None, "stdout": ""},
    ]
    report = run(ScriptedSandbox(lines, RunOutcome(exit_code=0)))
    assert report.verdict == "AC"


@pytest.mark.parametrize(
    ("samples", "expected"),
    [(True, "Segmentation fault"), (False, HIDDEN_ERROR)],
)
def test_native_crash_is_named_only_when_all_samples(samples, expected):
    tests = [TestInput({"blocks": [], "label": "a"}, [], samples)]
    sandbox = ScriptedSandbox([], RunOutcome(exit_code=139))
    report = run_tests(sandbox, CPP, "code", SIG, tests, "exact", LIMITS)
    assert report.verdict == "RE"
    assert expected in report.error


def test_compiled_languages_get_memory_and_compile_budget():
    sandbox = ScriptedSandbox([], RunOutcome(exit_code=0))
    run(sandbox, JAVA)
    assert sandbox.request is not None
    assert sandbox.request.memory_mb == LIMITS["memory_mb"] + JAVA.memory_overhead_mb
    assert sandbox.request.startup_s >= 10
