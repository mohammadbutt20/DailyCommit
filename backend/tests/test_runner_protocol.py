"""The runner's trust rules, without Docker: protocol order and worker-measured time
(ResultStream), opaque runs, the memory check, and two-phase judging."""

import json

import pytest

from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import RunOutcome, RunRequest, memory_exhausted
from dailycommit.sandbox.languages import CPP, PYTHON
from dailycommit.sandbox.runner import (
    HIDDEN_COMPILE_ERROR,
    HIDDEN_ERROR,
    TIMING_SLACK_MS,
    ResultStream,
    TestInput,
    judge_submission,
    run_tests,
)

MARK = "@@m@@"
SIG = Signature.model_validate(
    {"function": "f", "params": [{"name": "n", "type": "int"}], "returns": "int"}
)
LIMITS = {"time_ms": 1000, "memory_mb": 64}


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def stream(n_tests=3, reveal=True):
    clock = Clock()
    tests = [TestInput({"n": i}, i, True) for i in range(n_tests)]
    events: list[dict] = []
    return ResultStream(tests, MARK, 1000, "exact", reveal, events.append, clock), clock, events


def line(obj) -> str:
    return MARK + json.dumps(obj)


def result(i, out=None, ms=1, **extra):
    return line({"i": i, "out": i if out is None else out, "ms": ms, "err": None, **extra})


# --- protocol order ---------------------------------------------------------------------------


def test_only_the_first_ready_is_progress():
    s, clock, _ = stream()
    assert s.feed(line({"ready": True})) is True
    clock.t = 0.5
    assert s.feed(line({"ready": True})) is False  # forged: buys no time
    assert s.feed(result(0)) is True
    assert s.feed(line({"ready": True})) is False


def test_results_count_only_in_order_and_after_ready():
    s, _, _ = stream()
    assert s.feed(result(0)) is False  # before ready
    s.feed(line({"ready": True}))
    assert s.feed(result(1)) is False  # ahead of order
    assert s.feed(result(0)) is True
    assert s.feed(result(0, out=99)) is False  # duplicate: the first one stands
    assert s.feed(result(1)) is True
    assert s.feed(result(5)) is False  # out of range
    assert [o.verdict for o in s.outcomes.values()] == ["AC", "AC"]


@pytest.mark.parametrize(
    "msg", [{"done": True}, {"ce": "x"}, {"fatal": "x"}, {"ce_stderr": True}, [1], "junk"]
)
def test_other_lines_are_never_progress(msg):
    s, _, _ = stream()
    s.feed(line({"ready": True}))
    assert s.feed(line(msg) if not isinstance(msg, str) else MARK + msg) is False


def test_unmarked_lines_are_ignored():
    s, _, _ = stream()
    assert s.feed(json.dumps({"ready": True})) is False


# --- worker-measured time ------------------------------------------------------------------


def test_forged_low_time_is_tle_by_our_clock():
    s, clock, events = stream()
    s.feed(line({"ready": True}))
    clock.t = 1.5  # 1500 ms later, while the line claims 1 ms
    s.feed(result(0, ms=1))
    assert s.outcomes[0].verdict == "TLE"
    assert s.outcomes[0].time_ms == 1500 - TIMING_SLACK_MS
    assert events[0]["data"] == {"i": 0, "verdict": "TLE", "ms": 1500 - TIMING_SLACK_MS}


def test_slack_forgives_relay_overhead_but_no_more():
    s, clock, _ = stream()
    s.feed(line({"ready": True}))
    clock.t = (1000 + TIMING_SLACK_MS) / 1000  # exactly at the limit after slack
    s.feed(result(0, ms=900))
    clock.t += (1000 + TIMING_SLACK_MS + 10) / 1000  # 10 ms over
    s.feed(result(1, ms=900))
    assert [s.outcomes[0].verdict, s.outcomes[1].verdict] == ["AC", "TLE"]


def test_reported_time_can_only_make_it_stricter():
    s, clock, _ = stream()
    s.feed(line({"ready": True}))
    clock.t = 0.01
    s.feed(result(0, ms=1200))  # says it was slow: believed
    assert s.outcomes[0].verdict == "TLE" and s.outcomes[0].time_ms == 1200


def test_each_test_is_timed_from_the_previous_progress_line():
    s, clock, _ = stream()
    clock.t = 5.0  # interpreter start / compile time doesn't count
    s.feed(line({"ready": True}))
    clock.t = 5.4
    s.feed(result(0))
    clock.t = 6.6  # 1200 ms after test 0
    s.feed(result(1))
    assert s.outcomes[0].verdict == "AC" and s.outcomes[1].time_ms == 1200 - TIMING_SLACK_MS


# --- opaque runs ------------------------------------------------------------------------------


class Scripted:
    """Replays harness lines (marker added) and returns a fixed outcome; records each run."""

    def __init__(self, lines, outcome=None) -> None:
        self.lines, self.outcome, self.requests = lines, outcome or RunOutcome(exit_code=0), []

    def run(self, req: RunRequest, on_line) -> RunOutcome:
        self.requests.append(req)
        mark = req.argv[-1] if req.argv[-1].startswith("@@") else req.argv[2]
        for obj in self.lines(req) if callable(self.lines) else self.lines:
            on_line(mark + (obj if isinstance(obj, str) else json.dumps(obj)))
        return self.outcome


def harness_lines(n, out="secret", err=None):
    return [{"ready": True}] + [
        {"i": i, "out": out, "ms": 1, "err": err, "stdout": "printed secret"} for i in range(n)
    ]


MIXED = [TestInput({"n": 1}, "ok", True), TestInput({"n": 2}, "ok", False)]


def test_a_run_with_hidden_inputs_returns_no_program_text():
    report = run_tests(Scripted(harness_lines(2)), PYTHON, "code", SIG, MIXED, "exact", LIMITS)
    for r in report.results:
        assert r.actual is None and r.stdout is None
    report = run_tests(
        Scripted(harness_lines(2, err="secret trace")), PYTHON, "code", SIG, MIXED, "exact", LIMITS
    )
    assert {r.error for r in report.results} == {HIDDEN_ERROR}


def test_compile_error_text_is_hidden_when_hidden_inputs_are_present():
    sandbox = Scripted([{"ce": "error near: secret"}])
    assert (
        run_tests(sandbox, CPP, "code", SIG, MIXED, "exact", LIMITS).error == HIDDEN_COMPILE_ERROR
    )
    samples = [MIXED[0]]
    assert "secret" in run_tests(sandbox, CPP, "code", SIG, samples, "exact", LIMITS).error


def test_crash_detail_is_hidden_when_hidden_inputs_are_present():
    sandbox = Scripted([{"ready": True}], RunOutcome(exit_code=1, stderr="Traceback: secret"))
    report = run_tests(sandbox, PYTHON, "code", SIG, MIXED, "exact", LIMITS)
    assert report.results[0].error == HIDDEN_ERROR


def test_trusted_callers_may_reveal():
    report = run_tests(
        Scripted(harness_lines(2)), PYTHON, "code", SIG, MIXED, "exact", LIMITS, reveal_output=True
    )
    assert report.results[0].stdout == "printed secret"


# --- memory ----------------------------------------------------------------------------------


def stats(usage, limit, inactive=0, v1=False):
    key = "total_inactive_file" if v1 else "inactive_file"
    return {"memory_stats": {"usage": usage, "limit": limit, "stats": {key: inactive}}}


@pytest.mark.parametrize(
    ("payload", "full"),
    [
        (stats(95, 100), True),
        (stats(90, 100), True),
        (stats(89, 100), False),
        (stats(99, 100, inactive=20), False),  # reclaimable page cache isn't pressure
        (stats(95, 100, v1=True), True),
        (stats(95, 0), False),
        ({"memory_stats": {}}, False),  # container already gone
        ({}, False),
        (None, False),
        ({"memory_stats": {"usage": "x", "limit": 1}}, False),
    ],
)
def test_memory_exhausted(payload, full):
    assert memory_exhausted(payload) is full


@pytest.mark.parametrize(
    ("outcome", "verdict"),
    [
        (RunOutcome(exit_code=137, timed_out=True, memory_exhausted=True), "MLE"),
        (RunOutcome(exit_code=137, timed_out=True), "TLE"),
        (RunOutcome(exit_code=137, oom_killed=True), "MLE"),
        (RunOutcome(exit_code=137), "MLE"),
    ],
)
def test_memory_verdicts(outcome, verdict):
    report = run_tests(
        Scripted([{"ready": True}], outcome), PYTHON, "c", SIG, MIXED, "exact", LIMITS
    )
    assert report.results[0].verdict == verdict


# --- two-phase judging ----------------------------------------------------------------------


def test_samples_then_hidden_in_separate_containers():
    def lines(req):
        n = len(json.loads(req.files["inputs.json"]))
        return [{"ready": True}] + [{"i": i, "out": "ok", "ms": 1, "err": None} for i in range(n)]

    sandbox, events = Scripted(lines), []
    tests = [*MIXED, TestInput({"n": 3}, "ok", False)]
    report = judge_submission(sandbox, PYTHON, "c", SIG, tests, "exact", LIMITS, events.append)
    assert [json.loads(r.files["inputs.json"]) for r in sandbox.requests] == [
        [{"n": 1}],
        [{"n": 2}, {"n": 3}],
    ]
    assert (report.verdict, report.passed, report.total) == ("AC", 3, 3)
    assert [r.ordinal for r in report.results] == [0, 1, 2]
    assert [e["data"]["i"] for e in events] == [0, 1, 2]  # hidden ordinals continue the samples


def test_a_failed_sample_skips_the_hidden_tests():
    sandbox = Scripted(harness_lines(1, out="wrong"))
    tests = [*MIXED, TestInput({"n": 3}, "ok", False)]
    report = judge_submission(sandbox, PYTHON, "c", SIG, tests, "exact", LIMITS)
    assert len(sandbox.requests) == 1
    assert [r.verdict for r in report.results] == ["WA", "skipped", "skipped"]
    assert (report.passed, report.total) == (0, 3)
    assert report.results[0].actual == "wrong"  # sample details still shown


def test_sample_compile_error_shows_the_compiler_output():
    report = judge_submission(
        Scripted([{"ce": "line 3: oops"}]), CPP, "c", SIG, MIXED, "exact", LIMITS
    )
    assert (report.verdict, report.error) == ("CE", "line 3: oops")


def test_input_dependent_compile_error_in_the_hidden_run_is_opaque():
    def lines(req):
        hidden_run = {"n": 2} in json.loads(req.files["inputs.json"])
        if hidden_run:
            return [{"ce": 'SyntaxError: [{"n": 2}]'}]
        return [{"ready": True}, {"i": 0, "out": "ok", "ms": 1, "err": None}]

    report = judge_submission(Scripted(lines), PYTHON, "c", SIG, MIXED, "exact", LIMITS)
    assert [r.verdict for r in report.results] == ["AC", "RE"]
    assert report.error == HIDDEN_ERROR and report.results[1].error == HIDDEN_ERROR


def test_samples_must_come_first():
    with pytest.raises(ValueError):
        judge_submission(Scripted([]), PYTHON, "c", SIG, MIXED[::-1], "exact", LIMITS)
