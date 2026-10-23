"""Adversarial submissions against the real Docker sandbox. Run with `make test-sandbox`
(inside the worker container, which has the Docker socket and the sandbox images built)."""

import time

import pytest

from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import SANDBOX_LABEL, DockerSandbox
from dailycommit.sandbox.languages import PYTHON
from dailycommit.sandbox.runner import TestInput, run_tests

pytestmark = pytest.mark.sandbox

SIG = Signature.model_validate(
    {"function": "solve", "params": [{"name": "n", "type": "int"}], "returns": "string"}
)
LIMITS = {"time_ms": 1000, "memory_mb": 64}


@pytest.fixture(scope="module")
def sandbox() -> DockerSandbox:
    return DockerSandbox()


def run(sandbox, body: str, samples: bool = True):
    code = "class Solution:\n    def solve(self, n):\n" + "".join(
        f"        {line}\n" for line in body.strip().splitlines()
    )
    tests = [TestInput({"n": 1}, "ok", samples), TestInput({"n": 2}, "ok", samples)]
    return run_tests(sandbox, PYTHON, code, SIG, tests, "exact", LIMITS)


def test_accepts_normal_code(sandbox):
    assert run(sandbox, "return 'ok'").verdict == "AC"


def test_infinite_loop_is_tle_and_fast(sandbox):
    start = time.monotonic()
    report = run(sandbox, "while True: pass")
    assert report.verdict == "TLE"
    assert [r.verdict for r in report.results] == ["TLE", "skipped"]
    assert time.monotonic() - start < 10


def test_memory_bomb_is_mle(sandbox):
    report = run(sandbox, "x = [bytearray(10**6) for _ in range(10**4)]\nreturn 'ok'")
    assert report.verdict == "MLE"


def test_fork_bomb_is_contained(sandbox):
    body = "import os\nwhile True:\n    try: os.fork()\n    except OSError: pass"
    report = run(sandbox, body)
    assert report.verdict in {"TLE", "RE", "MLE"}


def test_no_network(sandbox):
    body = "import socket\nsocket.create_connection(('1.1.1.1', 80), timeout=2)\nreturn 'ok'"
    assert run(sandbox, body).verdict == "RE"


def test_cannot_write_outside_work(sandbox):
    assert run(sandbox, "open('/etc/pwned', 'w').write('x')\nreturn 'ok'").verdict == "RE"


def test_disk_fill_is_contained(sandbox):
    body = "f = open('/work/big', 'wb')\nwhile True: f.write(b'x' * 10**6)"
    assert run(sandbox, body).verdict in {"RE", "TLE"}


def test_huge_output_is_cut_off(sandbox):
    body = "import sys\nwhile True: sys.__stdout__.write('x' * 10**5)"
    assert run(sandbox, body).verdict in {"RE", "TLE"}


def test_environment_has_no_secrets(sandbox):
    body = "import os\nleak = [k for k in os.environ if 'DATABASE' in k or 'REDIS' in k]\nreturn 'ok' if not leak else str(leak)"
    assert run(sandbox, body).verdict == "AC"


def test_runs_as_nobody(sandbox):
    assert (
        run(sandbox, "import os\nreturn 'ok' if os.getuid() == 65534 else str(os.getuid())").verdict
        == "AC"
    )


def test_no_containers_left_behind(sandbox):
    run(sandbox, "while True: pass")
    leftover = sandbox.client.containers.list(all=True, filters={"label": SANDBOX_LABEL})
    assert leftover == []
