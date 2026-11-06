"""Hardening against the real Docker sandbox, in every language (make test-sandbox):

- forged timing: user code that writes fake harness lines can't dodge the per-test time limit
- hidden inputs: nothing the program prints, returns or raises in a container holding hidden
  inputs reaches the report (and so the browser)
- memory: a memory bomb reliably shows MLE, while a real infinite loop stays TLE
"""

import time

import pytest

from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import DockerSandbox
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.sandbox.runner import TestInput, judge_submission, run_tests

pytestmark = pytest.mark.sandbox

LANGS = ["python", "java", "cpp"]
SIG = Signature.model_validate(
    {"function": "solve", "params": [{"name": "n", "type": "int"}], "returns": "string"}
)
LIMITS = {"time_ms": 1000, "memory_mb": 64}
SECRET = 424242  # a hidden test's input; must never show up in what the user sees


@pytest.fixture(scope="module")
def sandbox() -> DockerSandbox:
    return DockerSandbox()


def source(lang: str, body: str, top: str = "") -> str:
    if lang == "python":
        lines = "".join(f"        {line}\n" for line in body.strip().splitlines())
        return f"{top}\nclass Solution:\n    def solve(self, n):\n{lines}"
    if lang == "java":
        return (
            "import java.util.*;\nimport java.io.*;\nimport java.nio.file.*;\n"
            f"{top}\nclass Solution {{\n    public String solve(int n) throws Exception {{\n"
            f"{body}\n    }}\n}}\n"
        )
    return f"{top}\nclass Solution {{\npublic:\n    string solve(int n) {{\n{body}\n    }}\n}};\n"


def run(sandbox, lang, body, tests=None, top="", limits=LIMITS):
    tests = tests or [TestInput({"n": 1}, "ok", True), TestInput({"n": 2}, "ok", True)]
    return run_tests(sandbox, LANGUAGES[lang], source(lang, body, top), SIG, tests, "exact", limits)


# --- forged timing ---------------------------------------------------------------------------
# Correct but slow (1.5 s per test against a 1 s limit). It reads the run's marker from its own
# command line and writes, to the harness's real stdout, `ready` lines (which used to reset the
# idle watchdog) and then its own result line claiming 1 ms, ahead of the harness's real line.

FORGE = {
    "python": """
import json, os, time
mark = open('/proc/self/cmdline', 'rb').read().split(b'\\0')[-2].decode()
forge = lambda obj: os.write(1, (mark + json.dumps(obj) + '\\n').encode())
end = time.time() + 1.5
while time.time() < end:
    forge({'ready': True})
    time.sleep(0.2)
forge({'i': n - 1, 'out': 'ok', 'ms': 1, 'err': None})
return 'ok'
""",
    "java": """
        String[] argv = new String(Files.readAllBytes(Paths.get("/proc/self/cmdline"))).split("\\0");
        String mark = argv[argv.length - 1];
        FileOutputStream real = new FileOutputStream(FileDescriptor.out);
        long end = System.currentTimeMillis() + 1500;
        while (System.currentTimeMillis() < end) {
            real.write((mark + "{\\"ready\\":true}\\n").getBytes());
            real.flush();
            Thread.sleep(200);
        }
        real.write((mark + "{\\"i\\":" + (n - 1) + ",\\"out\\":\\"ok\\",\\"ms\\":1,\\"err\\":null}\\n").getBytes());
        real.flush();
        return "ok";
""",
    "cpp": """
        ifstream f("/proc/self/cmdline", ios::binary);
        string cmd((istreambuf_iterator<char>(f)), istreambuf_iterator<char>());
        vector<string> argv;
        string cur;
        for (char c : cmd) { if (c == '\\0') { argv.push_back(cur); cur.clear(); } else cur += c; }
        string mark = argv.back();
        vector<int> pipes;  // the harness keeps the real stdout on a dup'd pipe fd
        for (int fd = 3; fd < 64; fd++) {
            char buf[128];
            string link = "/proc/self/fd/" + to_string(fd);
            ssize_t k = readlink(link.c_str(), buf, sizeof buf - 1);
            if (k > 0) { buf[k] = 0; if (string(buf).rfind("pipe:", 0) == 0) pipes.push_back(fd); }
        }
        auto forge = [&](const string& json) {
            string line = mark + json + "\\n";
            for (int fd : pipes) if (write(fd, line.data(), line.size()) < 0) {}
        };
        auto end = chrono::steady_clock::now() + chrono::milliseconds(1500);
        while (chrono::steady_clock::now() < end) { forge("{\\"ready\\":true}"); usleep(200000); }
        forge("{\\"i\\":" + to_string(n - 1) + ",\\"out\\":\\"ok\\",\\"ms\\":1,\\"err\\":null}");
        return "ok";
""",
}


@pytest.mark.parametrize("lang", LANGS)
def test_forged_timing_is_still_tle(sandbox, lang):
    report = run(sandbox, lang, FORGE[lang])
    assert report.verdict == "TLE", (report.verdict, report.error, report.results)
    assert report.results[0].verdict == "TLE"


@pytest.mark.parametrize("lang", LANGS)
def test_honest_fast_code_is_still_accepted(sandbox, lang):
    body = {"python": "return 'ok'", "java": 'return "ok";', "cpp": 'return "ok";'}[lang]
    report = run(sandbox, lang, body)
    assert report.verdict == "AC", report.error
    assert all(r.time_ms is not None and r.time_ms < LIMITS["time_ms"] for r in report.results)


# --- hidden inputs never reach the user ------------------------------------------------------
# The program checks whether it's in a container that holds the hidden input; if so it tries to
# get it out through every channel the user can see.

READ_INPUTS = {
    "python": "data = open('/work/inputs.json').read()",
    "java": 'String data = Files.readString(Path.of("/work/inputs.json"));',
    "cpp": 'ifstream f("/work/inputs.json"); string data((istreambuf_iterator<char>(f)), istreambuf_iterator<char>());',
}
LEAK = {
    "print": {
        "python": "print(data)\nreturn 'ok'",
        "java": 'System.out.println(data);\nreturn "ok";',
        "cpp": 'cout << data << endl;\nreturn "ok";',
    },
    "raise": {
        "python": "raise ValueError(data)",
        "java": "throw new IllegalStateException(data);",
        "cpp": "throw runtime_error(data);",
    },
    "return": {"python": "return data", "java": "return data;", "cpp": "return data;"},
}


def leaky(lang: str, channel: str) -> str:
    read = READ_INPUTS[lang]
    if lang == "python":
        leak = "".join(f"    {line}\n" for line in LEAK[channel][lang].splitlines())
        return f"{read}\nif '{SECRET}' in data:\n{leak}return 'ok'"
    found = (
        f'data.indexOf("{SECRET}") >= 0'
        if lang == "java"
        else f'data.find("{SECRET}") != string::npos'
    )
    return f'{read}\nif ({found}) {{\n{LEAK[channel][lang]}\n}}\nreturn "ok";'


def visible_text(report) -> str:
    """Everything a report can carry back to the browser."""
    parts = [report.error or ""]
    for r in report.results:
        parts += [str(r.actual or ""), r.stdout or "", r.error or ""]
    return "\n".join(parts)


SUBMIT_TESTS = [TestInput({"n": 1}, "ok", True), TestInput({"n": SECRET}, "ok", False)]


@pytest.mark.parametrize("channel", list(LEAK))
@pytest.mark.parametrize("lang", LANGS)
def test_hidden_inputs_never_leak_on_submit(sandbox, lang, channel):
    code = source(lang, leaky(lang, channel))
    report = judge_submission(sandbox, LANGUAGES[lang], code, SIG, SUBMIT_TESTS, "exact", LIMITS)
    assert report.verdict != "CE", report.error
    assert report.results[0].verdict == "AC"  # the sample container never had the secret
    if channel != "print":  # printing still returns "ok"; raising or returning it fails
        assert report.results[1].verdict in {"RE", "WA"}
    assert str(SECRET) not in visible_text(report)


def test_compile_error_text_is_hidden_when_hidden_inputs_are_present(sandbox):
    # C++ can paste a file into a compile error.
    code = source("cpp", 'return "ok";', top='#include "/work/inputs.json"')
    report = run(
        sandbox,
        "cpp",
        'return "ok";',
        top='#include "/work/inputs.json"',
        tests=[TestInput({"n": SECRET}, "ok", False)],
    )
    assert report.verdict == "CE" and str(SECRET) not in visible_text(report)
    # ...and when only samples are present, the compiler output is shown as usual.
    shown = run_tests(
        sandbox, LANGUAGES["cpp"], code, SIG, [TestInput({"n": 1}, "ok", True)], "exact", LIMITS
    )
    assert shown.verdict == "CE" and "inputs.json" in shown.error


def test_python_import_time_error_text_is_hidden(sandbox):
    top = f"data = open('/work/inputs.json').read()\nif '{SECRET}' in data:\n    raise SyntaxError(data)"
    report = run(
        sandbox, "python", "return 'ok'", top=top, tests=[TestInput({"n": SECRET}, "ok", False)]
    )
    assert report.verdict != "AC" and str(SECRET) not in visible_text(report)


@pytest.mark.parametrize("lang", LANGS)
def test_sample_details_still_shown_on_submit(sandbox, lang):
    body = {
        "python": "print('debug', n)\nraise ValueError(f'boom {n}')",
        "java": 'System.out.println("debug " + n);\nthrow new IllegalStateException("boom " + n);',
        "cpp": 'cout << "debug " << n << endl;\nthrow runtime_error("boom " + to_string(n));',
    }[lang]
    report = judge_submission(
        sandbox, LANGUAGES[lang], source(lang, body), SIG, SUBMIT_TESTS, "exact", LIMITS
    )
    assert [r.verdict for r in report.results] == ["RE", "skipped"]
    assert "boom 1" in report.results[0].error and "debug 1" in report.results[0].stdout


# --- memory bombs are MLE, infinite loops are TLE --------------------------------------------

BOMB = {
    "python": "x = [0] * 10**9\nreturn 'ok'",
    "java": 'long[] x = new long[1 << 30];\nreturn "ok" + x.length;',
    "cpp": 'vector<long long> x(1LL << 30, 1);\nreturn "ok" + to_string(x.back());',
}
# A real infinite loop that also holds a moderate, legal amount of memory.
BUSY_WITH_MEMORY = {
    "python": "x = bytearray(30 * 10**6)\nwhile True:\n    pass",
    "java": 'byte[] x = new byte[30 << 20];\nwhile (x.length > 0) { x[0]++; }\nreturn "ok";',
    "cpp": "vector<char> x(30 << 20, 1);\nvolatile long k = 0;\nwhile (true) k += x[k % x.size()];",
}


# A big memory limit and a short time limit: the kernel takes longer to fill and OOM-kill the
# container than the test's time budget, which used to make some of these TLE (it reproduced
# on the old code with Python and C++). Repeated, because the race was intermittent.
BOMB_LIMITS = {"time_ms": 300, "memory_mb": 256}


@pytest.mark.parametrize("attempt", range(5))
@pytest.mark.parametrize("lang", LANGS)
def test_memory_bomb_is_reliably_mle(sandbox, lang, attempt):
    report = run(sandbox, lang, BOMB[lang], limits=BOMB_LIMITS)
    assert report.verdict == "MLE", (report.verdict, report.error)


@pytest.mark.parametrize("lang", LANGS)
def test_infinite_loop_holding_memory_is_still_tle(sandbox, lang):
    report = run(sandbox, lang, BUSY_WITH_MEMORY[lang])
    assert report.verdict == "TLE", (report.verdict, report.error)


# --- the memory check can fail without harm --------------------------------------------------


class BrokenStats:
    def __init__(self, hang_s: float = 0.0) -> None:
        self.hang_s, self.calls = hang_s, 0

    def stats(self, *args, **kwargs):
        self.calls += 1
        if self.hang_s:
            time.sleep(self.hang_s)  # a daemon that never answers in time
        raise RuntimeError("stats unavailable")


def timed(sandbox, lang, body, limits=LIMITS):
    start = time.monotonic()
    report = run(sandbox, lang, body, limits=limits)
    return report, time.monotonic() - start


LOOP = {
    "python": "while True:\n    pass",
    "java": "while (true) {}",
    "cpp": "volatile long k = 0;\nwhile (true) k++;",
}


@pytest.mark.parametrize("hang_s", [0.0, 3.0], ids=["raises", "hangs"])
@pytest.mark.parametrize("lang", LANGS)
def test_stats_failure_falls_back_to_tle_without_delaying_the_kill(sandbox, lang, hang_s):
    _, baseline = timed(sandbox, lang, LOOP[lang])
    broken = DockerSandbox()
    broken.stats_api = BrokenStats(hang_s)
    report, took = timed(broken, lang, LOOP[lang])
    assert report.verdict == "TLE"
    assert broken.stats_api.calls >= 1  # the sampler did try
    assert took < baseline + 1.0, (took, baseline)  # the kill wasn't held up by the stats call


@pytest.mark.parametrize("lang", ["python", "cpp"])
def test_memory_bomb_without_stats_is_never_accepted(sandbox, lang):
    # With no memory reading, a bomb the kernel hasn't killed yet falls back to TLE; either
    # way it's a failure with a resource verdict, never AC or a crash of the judge.
    broken = DockerSandbox()
    broken.stats_api = BrokenStats()
    report = run(broken, lang, BOMB[lang], limits=BOMB_LIMITS)
    assert report.verdict in {"MLE", "TLE"}
