"""Reading and validating problems/<slug>/ folders. No database access."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from dailycommit.problems.schema import ProblemSpec, TestSpec, check_value, compare_json
from dailycommit.sandbox.languages import LANGUAGES


class ProblemError(Exception):
    pass


@dataclass
class LoadedProblem:
    spec: ProblemSpec
    statement_md: str
    tests: list[TestSpec]
    solutions: dict[str, str]  # language id -> reference solution source
    content_hash: str

    @property
    def compare(self):
        return compare_json(self.spec.compare)


def load_problem(path: Path) -> LoadedProblem:
    def read(name: str) -> bytes:
        f = path / name
        if not f.is_file():
            raise ProblemError(f"{path.name}: missing {name}")
        return f.read_bytes()

    raw_spec, raw_statement, raw_tests = (
        read("problem.yaml"),
        read("statement.md"),
        read("tests.json"),
    )
    try:
        spec = ProblemSpec.model_validate(yaml.safe_load(raw_spec))
        tests = [TestSpec.model_validate(t) for t in json.loads(raw_tests)]
    except (ValidationError, ValueError, yaml.YAMLError) as e:
        raise ProblemError(f"{path.name}: {e}") from e
    if spec.slug != path.name:
        raise ProblemError(f"{path.name}: slug {spec.slug!r} must match the folder name")

    solutions = {}
    for lang in LANGUAGES.values():
        ref = path / "solutions" / f"ref{lang.extension}"
        if ref.is_file():
            solutions[lang.id] = ref.read_text()

    problem = LoadedProblem(
        spec=spec,
        statement_md=raw_statement.decode(),
        tests=tests,
        solutions=solutions,
        content_hash=hashlib.sha256(raw_spec + raw_statement + raw_tests).hexdigest(),
    )
    errors = validate(problem)
    if errors:
        raise ProblemError(f"{path.name}: " + "; ".join(errors))
    return problem


def validate(p: LoadedProblem) -> list[str]:
    errors: list[str] = []
    names = [param.name for param in p.spec.params]
    if not any(t.sample for t in p.tests):
        errors.append("needs at least one sample test")
    if not any(not t.sample for t in p.tests):
        errors.append("needs at least one hidden test")
    if not p.solutions:
        errors.append("needs a reference solution in solutions/")
    for n, t in enumerate(p.tests):
        if sorted(t.input) != sorted(names):
            errors.append(f"test {n}: input keys {sorted(t.input)} != params {sorted(names)}")
            continue
        for param in p.spec.params:
            if not check_value(param.type, t.input[param.name]):
                errors.append(f"test {n}: {param.name} is not a valid {param.type}")
        if not check_value(p.spec.returns, t.expected):
            errors.append(f"test {n}: expected is not a valid {p.spec.returns}")
    return errors


def load_all(root: Path) -> list[LoadedProblem]:
    if not root.is_dir():
        raise ProblemError(f"problems directory {root} not found")
    return [load_problem(d) for d in sorted(root.iterdir()) if d.is_dir()]
