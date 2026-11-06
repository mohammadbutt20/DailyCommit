"""Supported submission languages. To add one: a Language here, a codegen module, an image
under sandbox/images/, a line in the Makefile's sandbox-images, and ref solutions."""

import shlex
from collections.abc import Callable
from dataclasses import dataclass

from dailycommit.config import settings
from dailycommit.problems.schema import Signature
from dailycommit.sandbox.codegen import cpp
from dailycommit.sandbox.codegen import java as jv
from dailycommit.sandbox.codegen import python as py

# Printed (after the run's marker) when compilation fails; the runner then reports CE with the
# compiler's stderr. Only the wrapper below prints it, before any user code has run.
COMPILE_FAILED = '{"ce_stderr":true}'
COMPILE_ERROR_BYTES = 4000


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    monaco: str  # Monaco editor language id
    source_file: str
    extension: str  # of reference solutions: problems/<slug>/solutions/ref<extension>
    starter_code: Callable[[Signature], str]
    harness_files: Callable[[Signature], dict[str, str]]
    # argv run inside the container after the files are extracted into /work.
    # Gets the run's marker and the problem's memory limit in MB.
    run_command: Callable[[str, int], list[str]]
    startup_s: float  # budget before the first test result (interpreter start / compile)
    memory_overhead_mb: int  # runtime (and compiler) overhead on top of the problem's limit

    @property
    def image(self) -> str:
        return f"{settings.sandbox_image_prefix}{self.id}:latest"


# The C++ harness runs solutions on a thread with this much stack (codegen/cpp.py); the
# mapping counts toward the data limit below, so it's added on top.
CPP_SOLUTION_STACK_MB = 256


def _data_limit(mb: int) -> str:
    """`ulimit -d`: caps the program's heap (RLIMIT_DATA), so a huge allocation fails at once
    (MemoryError / bad_alloc, which the harnesses turn into exit 137 = MLE) instead of racing
    the kernel's OOM killer against the time limit. Set to the container's memory cap, so it
    never allows less memory than before. Not used for Java: the JVM's reserved address space
    doesn't fit it, and -Xmx already makes Java fail fast."""
    return f"ulimit -d {mb * 1024}"


def _compile_then_run(
    compile_argv: list[str], run_argv: list[str], mark: str, data_mb: int | None = None
) -> list[str]:
    """Compile inside the sandbox; on failure print the CE marker line and the compiler's
    output (to stderr), otherwise exec the program with the marker as its last argument. The
    data limit (if any) applies to the program only, never to the compiler."""
    limit = f"{_data_limit(data_mb)} && " if data_mb else ""
    script = (
        f"{shlex.join(compile_argv)} >/work/.ce 2>&1 || {{ "
        f"printf '%s%s\\n' \"$1\" {shlex.quote(COMPILE_FAILED)}; "
        f"head -c {COMPILE_ERROR_BYTES} /work/.ce >&2; exit 1; }}; "
        f'{limit}exec {shlex.join(run_argv)} "$1"'
    )
    return ["sh", "-c", script, "sh", mark]


PYTHON_OVERHEAD_MB = 32
CPP_OVERHEAD_MB = 96


PYTHON = Language(
    id="python",
    name="Python 3",
    monaco="python",
    source_file="solution.py",
    extension=".py",
    starter_code=py.starter_code,
    harness_files=lambda sig: {"harness.py": py.harness(sig)},
    run_command=lambda mark, mem: [
        "sh",
        "-c",
        f'{_data_limit(mem + PYTHON_OVERHEAD_MB)} && exec python3 /work/harness.py "$1"',
        "sh",
        mark,
    ],
    startup_s=3.0,
    memory_overhead_mb=PYTHON_OVERHEAD_MB,
)

_GSON = "/opt/gson/gson.jar"
# Lean JVM for one-shot runs: one GC thread, no perf-data file (the root is read-only anyway).
_JVM_FLAGS = ["-XX:+UseSerialGC", "-XX:-UsePerfData", "-XX:CICompilerCount=2"]

JAVA = Language(
    id="java",
    name="Java 21",
    monaco="java",
    source_file="Solution.java",
    extension=".java",
    starter_code=jv.starter_code,
    harness_files=lambda sig: {"Main.java": jv.harness(sig)},
    run_command=lambda mark, mem: _compile_then_run(
        [
            "javac",
            *(f"-J{f}" for f in _JVM_FLAGS),
            "-J-XX:TieredStopAtLevel=1",
            "-J-XX:SharedArchiveFile=/opt/javac.jsa",
            "-J-Xshare:auto",
            "-J-Xmx160m",
            "-encoding",
            "UTF-8",
            "-proc:none",
            "-nowarn",
            "-Xmaxerrs",
            "10",
            "-cp",
            _GSON,
            "-d",
            "/work",
            "/work/Solution.java",
            "/work/Main.java",
        ],
        ["java", *_JVM_FLAGS, f"-Xmx{mem}m", "-cp", f"/work:{_GSON}", "Main"],
        mark,
    ),
    startup_s=10.0,
    memory_overhead_mb=192,
)

# Must match the flags the C++ image precompiles <bits/stdc++.h> with (sandbox/images/cpp).
CPP_FLAGS = ["-std=c++17", "-O2", "-pipe"]

CPP = Language(
    id="cpp",
    name="C++17",
    monaco="cpp",
    source_file="solution.cpp",
    extension=".cpp",
    starter_code=cpp.starter_code,
    harness_files=lambda sig: {"main.cpp": cpp.harness(sig)},
    run_command=lambda mark, mem: _compile_then_run(
        [
            "g++",
            *CPP_FLAGS,
            "-include",
            "/opt/dc/pch.hpp",
            "-I/opt/dc",
            "-fmax-errors=10",
            "-fdiagnostics-color=never",
            "-o",
            "/work/main",
            "/work/main.cpp",
            "/opt/dc/dcio.o",
        ],
        ["/work/main"],
        mark,
        data_mb=mem + CPP_OVERHEAD_MB + CPP_SOLUTION_STACK_MB,
    ),
    startup_s=10.0,
    memory_overhead_mb=CPP_OVERHEAD_MB,
)

LANGUAGES: dict[str, Language] = {lang.id: lang for lang in (PYTHON, JAVA, CPP)}
