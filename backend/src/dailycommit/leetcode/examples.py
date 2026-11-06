"""LeetCode's worked examples, read out of an imported statement.

A judge pack's sample tests must be exactly LeetCode's examples (problems/README.md);
`python -m dailycommit.problems check-examples` compares them using this parser. Statements
are only read from the database (the import), never stored in the repo.

An example looks like (after dropping the HTML tags):

    Input: nums = [2,7,11,15], target = 9
    Output: [0,1]
"""

import html
import json
import re
from dataclasses import dataclass
from typing import Any

from dailycommit.sandbox.compare import outputs_match

_TAG = re.compile(r"<[^>]+>")
_INPUT = re.compile(r"Input:?\s*")
_OUTPUT = re.compile(r"\s*Output:?\s*")
_DECODER = json.JSONDecoder()


class ExampleParseError(ValueError):
    pass


@dataclass(frozen=True)
class Example:
    inputs: dict[str, Any]
    output: Any


def statement_text(statement_html: str) -> str:
    text = _TAG.sub("", statement_html.replace("<br>", "\n").replace("<br/>", "\n"))
    return html.unescape(text).replace("\xa0", " ")


def _decode(text: str, pos: int) -> tuple[Any, int]:
    """One JSON value starting at `pos` (strings may contain anything, e.g. ', t = ')."""
    try:
        return _DECODER.raw_decode(text, pos)
    except ValueError as e:
        raise ExampleParseError(f"not a JSON value: {text[pos : pos + 40]!r}") from e


def _parse_inputs_at(text: str, pos: int, params: list[str]) -> tuple[dict[str, Any], int]:
    values: dict[str, Any] = {}
    for n, name in enumerate(params):
        sep = r"\s*,\s*" if n else r"\s*"
        m = re.compile(sep + re.escape(name) + r"\s*=\s*").match(text, pos)
        if not m:
            raise ExampleParseError(
                f"expected {name!r} at {text[pos : pos + 40]!r} (parameters {params})"
            )
        values[name], pos = _decode(text, m.end())
    return values, pos


def parse_inputs(raw: str, params: list[str]) -> dict[str, Any]:
    """`nums = [2,7], target = 9` -> {"nums": [2, 7], "target": 9}"""
    values, end = _parse_inputs_at(raw, 0, params)
    if raw[end:].strip():
        raise ExampleParseError(f"unexpected {raw[end:]!r} after the inputs")
    return values


def parse_examples(statement_html: str, params: list[str]) -> list[Example]:
    text = statement_text(statement_html)
    examples = []
    for m in _INPUT.finditer(text):
        inputs, pos = _parse_inputs_at(text, m.end(), params)
        out = _OUTPUT.match(text, pos)
        if not out:
            raise ExampleParseError(f"no 'Output:' after the inputs at {text[pos : pos + 40]!r}")
        output, _ = _decode(text, out.end())
        examples.append(Example(inputs, output))
    if not examples:
        raise ExampleParseError("no 'Input: … Output: …' examples found")
    return examples


def sample_mismatches(
    samples: list[tuple[dict[str, Any], Any]], examples: list[Example], compare: Any
) -> list[str]:
    """How a pack's sample tests (input, expected) differ from LeetCode's examples: same
    count, same order, same inputs, and outputs equal under the pack's compare mode (an
    example may list a valid answer in another order where any order is accepted)."""
    problems = []
    if len(samples) != len(examples):
        problems.append(f"{len(samples)} samples but LeetCode has {len(examples)} examples")
    for n, ((inputs, expected), ex) in enumerate(zip(samples, examples, strict=False), 1):
        if inputs != ex.inputs:
            problems.append(f"sample {n}: input {inputs} != LeetCode's {ex.inputs}")
        elif not outputs_match(expected, ex.output, compare):
            problems.append(f"sample {n}: output {expected!r} != LeetCode's {ex.output!r}")
    return problems
