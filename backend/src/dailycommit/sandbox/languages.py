"""Supported submission languages. Java and C++ are later slices: add a Language here,
a codegen module, and an image under sandbox/images/."""

from collections.abc import Callable
from dataclasses import dataclass

from dailycommit.config import settings
from dailycommit.problems.schema import Signature
from dailycommit.sandbox.codegen import python as py


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    monaco: str  # Monaco editor language id
    source_file: str
    extension: str  # of reference solutions: problems/<slug>/solutions/ref<extension>
    starter_code: Callable[[Signature], str]
    harness_files: Callable[[Signature], dict[str, str]]
    # argv run inside the container after the files are extracted into /work. Gets the marker.
    run_command: Callable[[str], list[str]]
    startup_s: float  # budget before the first test result (interpreter start / compile)
    memory_overhead_mb: int  # runtime overhead added on top of the problem's memory limit

    @property
    def image(self) -> str:
        return f"{settings.sandbox_image_prefix}{self.id}:latest"


PYTHON = Language(
    id="python",
    name="Python 3",
    monaco="python",
    source_file="solution.py",
    extension=".py",
    starter_code=py.starter_code,
    harness_files=lambda sig: {"harness.py": py.harness(sig)},
    run_command=lambda mark: ["python3", "/work/harness.py", mark],
    startup_s=3.0,
    memory_overhead_mb=32,
)

LANGUAGES: dict[str, Language] = {lang.id: lang for lang in (PYTHON,)}
