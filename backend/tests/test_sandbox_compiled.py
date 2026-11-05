"""Adversarial Java and C++ submissions against the real Docker sandbox (make test-sandbox).
Same threats as the Python suite in test_sandbox_docker.py, plus the compile step.
Each body is the method body of `String solve(int n)`."""

import time

import pytest

from dailycommit.problems.loader import load_all
from dailycommit.problems.schema import Signature
from dailycommit.sandbox.backend import DockerSandbox
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.sandbox.runner import HIDDEN_ERROR, TestInput, run_tests
from tests.conftest import PROBLEMS_DIR

pytestmark = pytest.mark.sandbox

SIG = Signature.model_validate(
    {"function": "solve", "params": [{"name": "n", "type": "int"}], "returns": "string"}
)
LIMITS = {"time_ms": 1000, "memory_mb": 64}
COMPILED = ["java", "cpp"]

JAVA_PRELUDE = (
    "import java.util.*;\nimport java.io.*;\nimport java.nio.file.*;\nimport java.net.*;\n"
)
CPP_PRELUDE = "#include <sys/socket.h>\n#include <netinet/in.h>\n#include <arpa/inet.h>\n"


@pytest.fixture(scope="module")
def sandbox() -> DockerSandbox:
    return DockerSandbox()


def run(sandbox, lang: str, body: str, tests=None):
    if lang == "java":
        code = f"{JAVA_PRELUDE}class Solution {{\n    public String solve(int n) throws Exception {{\n{body}\n    }}\n}}\n"
    else:
        code = f"{CPP_PRELUDE}class Solution {{\npublic:\n    string solve(int n) {{\n{body}\n    }}\n}};\n"
    tests = tests or [TestInput({"n": 1}, "ok", True), TestInput({"n": 2}, "ok", True)]
    return run_tests(sandbox, LANGUAGES[lang], code, SIG, tests, "exact", LIMITS)


B = {
    "ok": {"java": 'return "ok";', "cpp": 'return "ok";'},
    "compile_error": {"java": 'return "ok"', "cpp": 'return "ok"'},
    "loop": {"java": "while (true) {}", "cpp": "volatile long x = 0; while (true) x++;"},
    "memory": {
        "java": "List<byte[]> l = new ArrayList<>();\nwhile (true) l.add(new byte[1 << 20]);",
        "cpp": 'vector<vector<char>> l;\nwhile (true) l.emplace_back(1 << 20, 1);\nreturn "ok";',
    },
    "fork": {
        "java": 'while (true) { try { new ProcessBuilder("sh", "-c", "sleep 60").start(); }'
        " catch (IOException e) {} }",
        "cpp": "while (true) fork();",
    },
    "network": {
        "java": 'new Socket().connect(new InetSocketAddress("1.1.1.1", 80), 2000);\nreturn "ok";',
        "cpp": "int s = socket(AF_INET, SOCK_STREAM, 0);\n"
        "sockaddr_in a{}; a.sin_family = AF_INET; a.sin_port = htons(80);\n"
        'inet_pton(AF_INET, "1.1.1.1", &a.sin_addr);\n'
        'if (s < 0 || connect(s, (sockaddr*)&a, sizeof a) != 0) throw runtime_error("no net");\n'
        'return "ok";',
    },
    "write_outside": {
        "java": 'Files.writeString(Path.of("/etc/pwned"), "x");\nreturn "ok";',
        "cpp": 'if (!fopen("/etc/pwned", "w")) throw runtime_error("read-only");\nreturn "ok";',
    },
    "disk_fill": {
        "java": 'try (var f = new FileOutputStream("/work/big")) {\n'
        "    byte[] b = new byte[1 << 20];\n    while (true) f.write(b);\n}",
        "cpp": 'FILE* f = fopen("/work/big", "wb"); vector<char> b(1 << 20, 1);\n'
        "while (true) fwrite(b.data(), 1, b.size(), f);",
    },
    "huge_output": {
        # Straight to the real stdout, past the harness's capture.
        "java": "var o = new FileOutputStream(FileDescriptor.out); byte[] b = new byte[100000];\n"
        "while (true) o.write(b);",
        "cpp": "string b(100000, 'x');\n"
        "while (true) for (int fd = 3; fd < 10; fd++) if (write(fd, b.data(), b.size()) < 0) {}",
    },
    "env": {
        "java": "for (String k : System.getenv().keySet())\n"
        '    if (k.contains("DATABASE") || k.contains("REDIS")) return k;\nreturn "ok";',
        "cpp": 'if (getenv("DATABASE_URL") || getenv("REDIS_URL")) return "leak";\nreturn "ok";',
    },
    "uid": {
        "java": 'for (String l : Files.readAllLines(Path.of("/proc/self/status")))\n'
        '    if (l.startsWith("Uid:")) return l.split("\\\\s+")[1].equals("65534") ? "ok" : l;\n'
        'return "?";',
        "cpp": 'return getuid() == 65534 ? "ok" : to_string(getuid());',
    },
    "deep_recursion": {
        lang: 'return depth(200000) == 200000 ? "ok" : "bad";\n    }\n'
        "    int depth(int k) { return k == 0 ? 0 : 1 + depth(k - 1);"
        for lang in COMPILED
    },
    "print_and_throw": {
        "java": 'System.out.println("debug " + n);\nthrow new IllegalStateException("boom " + n);',
        "cpp": 'cout << "debug " << n << endl;\nthrow runtime_error("boom " + to_string(n));',
    },
}


@pytest.mark.parametrize("lang", COMPILED)
def test_accepts_normal_code(sandbox, lang):
    report = run(sandbox, lang, B["ok"][lang])
    assert report.verdict == "AC", report.error


@pytest.mark.parametrize("lang", COMPILED)
def test_compile_error(sandbox, lang):
    report = run(sandbox, lang, B["compile_error"][lang])
    assert report.verdict == "CE"
    assert ("Solution.java" if lang == "java" else "solution.cpp") in report.error


@pytest.mark.parametrize("lang", COMPILED)
def test_infinite_loop_is_tle(sandbox, lang):
    start = time.monotonic()
    report = run(sandbox, lang, B["loop"][lang])
    assert report.verdict == "TLE"
    assert [r.verdict for r in report.results] == ["TLE", "skipped"]
    assert time.monotonic() - start < 20


@pytest.mark.parametrize("lang", COMPILED)
def test_memory_bomb_is_mle(sandbox, lang):
    report = run(sandbox, lang, B["memory"][lang])
    assert report.verdict == "MLE", report.error


@pytest.mark.parametrize("lang", COMPILED)
def test_fork_bomb_is_contained(sandbox, lang):
    assert run(sandbox, lang, B["fork"][lang]).verdict in {"TLE", "RE", "MLE"}


@pytest.mark.parametrize("lang", COMPILED)
@pytest.mark.parametrize("threat", ["network", "write_outside"])
def test_blocked_operations_fail(sandbox, lang, threat):
    report = run(sandbox, lang, B[threat][lang])
    assert report.verdict == "RE", report.error


@pytest.mark.parametrize("lang", COMPILED)
@pytest.mark.parametrize("threat", ["disk_fill", "huge_output"])
def test_resource_abuse_is_cut_off(sandbox, lang, threat):
    assert run(sandbox, lang, B[threat][lang]).verdict in {"RE", "TLE"}


@pytest.mark.parametrize("lang", COMPILED)
@pytest.mark.parametrize("check", ["env", "uid", "deep_recursion"])
def test_environment(sandbox, lang, check):
    report = run(sandbox, lang, B[check][lang])
    assert report.verdict == "AC", (report.error, [r.actual for r in report.results])


@pytest.mark.parametrize("lang", COMPILED)
def test_runtime_error_details_and_prints_only_on_samples(sandbox, lang):
    tests = [TestInput({"n": 1}, "ok", True), TestInput({"n": 2}, "ok", False)]
    report = run(sandbox, lang, B["print_and_throw"][lang], tests=tests)
    assert [r.verdict for r in report.results] == ["RE", "RE"]
    assert "boom 1" in report.results[0].error
    assert "debug 1" in report.results[0].stdout
    assert report.results[1].error == HIDDEN_ERROR and report.results[1].stdout is None


def test_cpp_segfault_is_named(sandbox):
    report = run(sandbox, "cpp", 'volatile int* p = nullptr; *p = n; return "ok";')
    assert report.verdict == "RE"
    assert "Segmentation fault" in report.error


@pytest.mark.parametrize("lang", COMPILED)
def test_starter_code_compiles_for_every_problem(sandbox, lang):
    language = LANGUAGES[lang]
    for p in load_all(PROBLEMS_DIR):
        tests = [TestInput(t.input, t.expected, t.sample) for t in p.tests]
        report = run_tests(
            sandbox,
            language,
            language.starter_code(p.spec.signature),
            p.spec.signature,
            tests,
            p.compare,
            p.spec.limits.model_dump(),
        )
        assert report.verdict in {"WA", "AC"}, (p.spec.slug, report.verdict, report.error)
