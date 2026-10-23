"""Runs one submission's tests in the sandbox and turns harness output into verdicts.

Synchronous (Docker SDK); the worker calls it in a thread. Independent of the database so
the problem validator can reuse it.
"""

import json
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import RunRequest, SandboxBackend
from dailycommit.sandbox.compare import outputs_match
from dailycommit.sandbox.languages import Language

HIDDEN_ERROR = "Runtime error on a hidden test"


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


def run_tests(
    sandbox: SandboxBackend,
    language: Language,
    code: str,
    signature: Signature,
    tests: Sequence[TestInput],
    compare: Any,
    limits: dict[str, int],
    on_event: EventHandler | None = None,
) -> RunReport:
    emit = on_event or (lambda _event: None)
    time_ms = limits["time_ms"]
    mark = "@@" + secrets.token_hex(8) + "@@"
    outcomes: dict[int, TestOutcome] = {}
    meta: dict[str, str] = {}

    def on_line(line: str) -> bool:
        if not line.startswith(mark):
            return False
        try:
            msg = json.loads(line[len(mark) :])
        except ValueError:
            return False
        if "ce" in msg or "fatal" in msg:
            meta.setdefault("ce" if "ce" in msg else "fatal", str(msg.get("ce") or msg["fatal"]))
            return True
        i = msg.get("i")
        if not isinstance(i, int) or not 0 <= i < len(tests) or i in outcomes:
            return "done" in msg
        outcomes[i] = _judge(i, tests[i], msg, compare, time_ms)
        emit({"event": "test", "data": _public(outcomes[i])})
        return True

    files = {
        language.source_file: code,
        "inputs.json": json.dumps([t.input for t in tests]),
        **language.harness_files(signature),
    }
    idle_s = time_ms / 1000 + 0.5
    req = RunRequest(
        image=language.image,
        files=files,
        argv=language.run_command(mark),
        memory_mb=limits["memory_mb"] + language.memory_overhead_mb,
        startup_s=language.startup_s,
        idle_s=idle_s,
        deadline_s=language.startup_s + idle_s * len(tests) + 2,
    )
    run = sandbox.run(req, on_line)

    if "ce" in meta:
        return RunReport("CE", 0, len(tests), None, meta["ce"])

    # The first test without a result is where the program died; the rest never ran.
    reveal_all = all(t.sample for t in tests)
    first_missing = next((i for i in range(len(tests)) if i not in outcomes), None)
    if first_missing is not None:
        if run.oom_killed or (run.exit_code == 137 and not run.timed_out):
            verdict, error = "MLE", None
        elif run.timed_out:
            verdict, error = "TLE", None
        elif run.output_exceeded:
            verdict, error = "RE", "Output limit exceeded"
        else:
            detail = meta.get("fatal") or run.stderr.strip() or f"exit code {run.exit_code}"
            verdict, error = "RE", detail if reveal_all else HIDDEN_ERROR
        outcomes[first_missing] = TestOutcome(first_missing, verdict, error=error)
        emit({"event": "test", "data": _public(outcomes[first_missing])})
        for i in range(first_missing + 1, len(tests)):
            outcomes[i] = TestOutcome(i, "skipped")

    results = [outcomes[i] for i in range(len(tests))]
    passed = sum(r.verdict == "AC" for r in results)
    failed = next((r for r in results if r.verdict != "AC"), None)
    times = [r.time_ms for r in results if r.time_ms is not None]
    return RunReport(
        verdict=failed.verdict if failed else "AC",
        passed=passed,
        total=len(tests),
        runtime_ms=max(times) if times else None,
        error=failed.error if failed else None,
        results=results,
    )


def _judge(i: int, test: TestInput, msg: dict[str, Any], compare: Any, time_ms: int) -> TestOutcome:
    ms = msg.get("ms") if isinstance(msg.get("ms"), int) else None
    # Hidden tests never reveal what the program printed or returned: either could echo the input.
    out = TestOutcome(i, "AC", time_ms=ms)
    if test.sample:
        out.actual = msg.get("out")
        out.stdout = msg.get("stdout") or None
    if msg.get("err"):
        out.verdict = "RE"
        out.error = str(msg["err"]) if test.sample else HIDDEN_ERROR
    elif ms is not None and ms > time_ms:
        out.verdict = "TLE"
    elif not outputs_match(msg.get("out"), test.expected, compare):
        out.verdict = "WA"
    return out


def _public(o: TestOutcome) -> dict[str, Any]:
    return {"i": o.ordinal, "verdict": o.verdict, "ms": o.time_ms}
