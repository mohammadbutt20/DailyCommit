import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from dailycommit.sandbox.backend import RunOutcome, RunRequest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBLEMS_DIR = Path(os.environ.get("PROBLEMS_DIR", REPO_ROOT / "problems"))


class LocalProcessSandbox:
    """TEST ONLY. Runs the generated harness as a plain subprocess, with no isolation, so the
    harness and runner logic can be tested without Docker. Only ever feed it trusted code."""

    def run(self, req: RunRequest, on_line) -> RunOutcome:
        with tempfile.TemporaryDirectory() as tmp:
            for name, content in req.files.items():
                Path(tmp, name).write_text(content, encoding="utf-8")
            argv = [sys.executable] + [a.replace("/work", tmp) for a in req.argv[1:]]
            proc = subprocess.Popen(
                argv,
                cwd=tmp,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            outcome = RunOutcome()
            timer = threading.Timer(
                req.deadline_s, lambda: (proc.kill(), setattr(outcome, "timed_out", True))
            )
            timer.start()
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    on_line(line.rstrip("\n"))
                proc.wait()
            finally:
                timer.cancel()
            outcome.exit_code = proc.returncode
            outcome.stderr = proc.stderr.read() if proc.stderr else ""
            time.sleep(0)
            return outcome


@pytest.fixture
def local_sandbox() -> LocalProcessSandbox:
    return LocalProcessSandbox()
