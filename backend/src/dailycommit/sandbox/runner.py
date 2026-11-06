"""Runs one submission's tests in the sandbox and turns harness output into verdicts.

Synchronous (Docker SDK); the worker calls it in a thread. Independent of the database so
the problem validator can reuse it.

Trust model. User code shares a process with the harness, so it can read the run's marker
and write lines that look like the harness's. Nothing such a line claims is trusted:
- Correctness: outputs are compared here, against expected values the container never sees.
- Time: the worker's own clock decides (`ResultStream`). Lines only count as progress in
  protocol order; a reported time can only make a verdict stricter.
- Information: a container that holds hidden-test inputs never returns anything the program
  controls (output, return values, error or compiler text); see `judge_submission`.
"""

import json
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import RunRequest, SandboxBackend
from dailycommit.sandbox.compare import outputs_match
from dailycommit.sandbox.languages import Language

HIDDEN_ERROR = "Runtime error on a hidden test"
HIDDEN_COMPILE_ERROR = "Compile error"
# Worker-measured time per test includes a little that isn't the program's: the harness
# (de)serializing values and Docker relaying the line. This much is forgiven, never more.
TIMING_SLACK_MS = 250
# Exit codes of natively compiled programs killed by a signal (128 + signal number).
_SIGNAL_EXITS = {
    134: "Aborted (SIGABRT)",
    136: "Arithmetic error, e.g. division by zero (SIGFPE)",
    139: "Segmentation fault (SIGSEGV): invalid memory access or stack overflow",
    153: "Output limit exceeded (SIGXFSZ)",
}


@dataclass(frozen=True)
class TestInput:
    __test__ = False

    input: dict[str, Any]
    expected: Any
    sample: bool


@dataclass
class TestOutcome:
    __test__ = False

    ordinal: int
    verdict: str  # AC WA TLE MLE RE skipped
    time_ms: int | None = None
    actual: Any = None
    stdout: str | None = None
    error: str | None = None


@dataclass
class RunReport:
    verdict: str  # AC WA TLE MLE RE CE
    passed: int
    total: int
    runtime_ms: int | None
    error: str | None
    results: list[TestOutcome] = field(default_factory=list)


EventHandler = Callable[[dict[str, Any]], None]


class ResultStream:
    """The harness protocol, read with the worker's clock.

    Progress (which resets the sandbox's idle watchdog) is only: the first `ready` line, then
    result lines strictly in order (i = 0, 1, 2, ...). Anything else - repeated `ready`/`done`,
    duplicates, results out of order or before `ready` - is ignored and buys no time. A test's
    time is the gap between its line and the previous progress line, as seen here.
    """

    def __init__(
        self,
        tests: Sequence[TestInput],
        mark: str,
        time_ms: int,
        compare: Any,
        reveal: bool,
        emit: EventHandler,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.tests, self.mark, self.time_ms, self.compare = tests, mark, time_ms, compare
        self.reveal, self.emit, self.clock = reveal, emit, clock
        self.outcomes: dict[int, TestOutcome] = {}
        self.meta: dict[str, str] = {}
        self.ready_at: float | None = None
        self.last_progress: float | None = None

    def feed(self, line: str) -> bool:
        if not line.startswith(self.mark):
            return False
        try:
            msg = json.loads(line[len(self.mark) :])
        except ValueError:
            return False
        if not isinstance(msg, dict):
            return False
        now = self.clock()
        if msg.get("ready") is True:
            if self.ready_at is not None or self.outcomes:
                return False  # only the first, before any result
            self.ready_at = self.last_progress = now
            return True
        if msg.get("ce_stderr") is True:
            self.meta.setdefault("ce_stderr", "1")  # the compiler's output is on stderr
            return False
        if "ce" in msg or "fatal" in msg:
            key = "ce" if "ce" in msg else "fatal"
            self.meta.setdefault(key, str(msg.get(key)))
            return False
        i = msg.get("i")
        if self.last_progress is None or i != len(self.outcomes) or i >= len(self.tests):
            return False  # before ready, out of order, a duplicate, or out of range
        observed_ms = round((now - self.last_progress) * 1000)
        self.last_progress = now
        self.outcomes[i] = self._judge(i, msg, observed_ms)
        self.emit({"event": "test", "data": _public(self.outcomes[i])})
        return True

    def _judge(self, i: int, msg: dict[str, Any], observed_ms: int) -> TestOutcome:
        test = self.tests[i]
        reported = msg.get("ms") if isinstance(msg.get("ms"), int) else 0
        # The program's own clock can only make this stricter; ours is the one that counts.
        ms = max(reported, observed_ms - TIMING_SLACK_MS, 0)
        out = TestOutcome(i, "AC", time_ms=ms)
        if self.reveal and test.sample:
            out.actual = msg.get("out")
            out.stdout = msg.get("stdout") or None
        if msg.get("err"):
            out.verdict = "RE"
            out.error = str(msg["err"]) if self.reveal and test.sample else HIDDEN_ERROR
        elif ms > self.time_ms:
            out.verdict = "TLE"
        elif not outputs_match(msg.get("out"), test.expected, self.compare):
            out.verdict = "WA"
        return out


def run_tests(
    sandbox: SandboxBackend,
    language: Language,
    code: str,
    signature: Signature,
    tests: Sequence[TestInput],
    compare: Any,
    limits: dict[str, int],
    on_event: EventHandler | None = None,
    reveal_output: bool | None = None,
) -> RunReport:
    """All `tests` in one container.

    `reveal_output`: whether anything the program controls (stdout, return values, error and
    compiler text) may appear in the report. Default: only if every test is a sample, because
    the container holds the inputs of every test it runs. Only trusted code (reference
    solutions in the problem validator) may pass True.
    """
    emit = on_event or (lambda _event: None)
    reveal = all(t.sample for t in tests) if reveal_output is None else reveal_output
    time_ms = limits["time_ms"]
    mark = "@@" + secrets.token_hex(8) + "@@"
    stream = ResultStream(tests, mark, time_ms, compare, reveal, emit)

    files = {
        language.source_file: code,
        "inputs.json": json.dumps([t.input for t in tests]),
        **language.harness_files(signature),
    }
    idle_s = time_ms / 1000 + 0.5
    req = RunRequest(
        image=language.image,
        files=files,
        argv=language.run_command(mark, limits["memory_mb"]),
        memory_mb=limits["memory_mb"] + language.memory_overhead_mb,
        startup_s=language.startup_s,
        idle_s=idle_s,
        deadline_s=language.startup_s + idle_s * len(tests) + 2,
    )
    run = sandbox.run(req, stream.feed)
    outcomes, meta = stream.outcomes, stream.meta

    if "ce_stderr" in meta and not outcomes:
        meta.setdefault("ce", run.stderr.strip() or "Compilation failed")
    if "ce" in meta:
        return RunReport("CE", 0, len(tests), None, meta["ce"] if reveal else HIDDEN_COMPILE_ERROR)

    # The first test without a result is where the program died; the rest never ran.
    first_missing = next((i for i in range(len(tests)) if i not in outcomes), None)
    if first_missing is not None:
        # Our own kills (timeout, output cap) also exit 137, so check them before guessing OOM.
        if run.oom_killed or run.memory_exhausted:
            verdict, error = "MLE", None
        elif run.timed_out:
            verdict, error = "TLE", None
        elif run.output_exceeded:
            verdict, error = "RE", "Output limit exceeded"
        elif run.exit_code == 137:
            verdict, error = "MLE", None
        else:
            detail = (
                meta.get("fatal")
                or run.stderr.strip()
                or _SIGNAL_EXITS.get(run.exit_code or 0)
                or f"exit code {run.exit_code}"
            )
            verdict, error = "RE", detail if reveal else HIDDEN_ERROR
        outcomes[first_missing] = TestOutcome(first_missing, verdict, error=error)
        emit({"event": "test", "data": _public(outcomes[first_missing])})
        for i in range(first_missing + 1, len(tests)):
            outcomes[i] = TestOutcome(i, "skipped")

    return _report([outcomes[i] for i in range(len(tests))])


def judge_submission(
    sandbox: SandboxBackend,
    language: Language,
    code: str,
    signature: Signature,
    tests: Sequence[TestInput],
    compare: Any,
    limits: dict[str, int],
    on_event: EventHandler | None = None,
) -> RunReport:
    """A Run or Submit, as the worker judges it. `tests` are samples first, then hidden ones
    (the order of services.testcases.tests_for_run).

    Samples run in their own container, with full details for the user. Only if they all pass
    do the hidden tests run, in a second container that returns verdicts and times only. So no
    output the program controls ever comes from a container that held a hidden input.
    """
    emit = on_event or (lambda _event: None)
    samples = [t for t in tests if t.sample]
    hidden = [t for t in tests if not t.sample]
    if tests[: len(samples)] != samples:
        raise ValueError("samples must come before hidden tests")
    if not samples or not hidden:
        return run_tests(sandbox, language, code, signature, tests, compare, limits, emit)

    first = run_tests(sandbox, language, code, signature, samples, compare, limits, emit)
    if first.verdict == "CE":  # compiler output from a samples-only container: safe to show
        return RunReport("CE", 0, len(tests), None, first.error)
    offset = len(samples)
    if first.verdict != "AC":
        return _report(first.results + _skipped(offset, len(hidden)))

    def shifted(event: dict[str, Any]) -> None:
        emit({**event, "data": {**event["data"], "i": event["data"]["i"] + offset}})

    second = run_tests(
        sandbox, language, code, signature, hidden, compare, limits, shifted, reveal_output=False
    )
    if second.verdict == "CE":
        # It compiled for the samples, so this came from the program reacting to its inputs
        # (e.g. raising SyntaxError at import). Opaque, like any hidden-test failure.
        failed = TestOutcome(offset, "RE", error=HIDDEN_ERROR)
        shifted({"event": "test", "data": _public(TestOutcome(0, "RE"))})
        return _report(first.results + [failed] + _skipped(offset + 1, len(hidden) - 1))
    for r in second.results:
        r.ordinal += offset
    return _report(first.results + second.results)


def _skipped(start: int, count: int) -> list[TestOutcome]:
    return [TestOutcome(start + j, "skipped") for j in range(count)]


def _report(results: list[TestOutcome]) -> RunReport:
    passed = sum(r.verdict == "AC" for r in results)
    failed = next((r for r in results if r.verdict != "AC"), None)
    times = [r.time_ms for r in results if r.time_ms is not None]
    return RunReport(
        verdict=failed.verdict if failed else "AC",
        passed=passed,
        total=len(results),
        runtime_ms=max(times) if times else None,
        error=failed.error if failed else None,
        results=results,
    )


def _public(o: TestOutcome) -> dict[str, Any]:
    return {"i": o.ordinal, "verdict": o.verdict, "ms": o.time_ms}
