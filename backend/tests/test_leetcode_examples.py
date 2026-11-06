"""Reading LeetCode's examples out of a statement (for `make check-examples`). The fixtures
mimic LeetCode's two statement layouts; they are made up, not copied statements."""

import pytest

from dailycommit.leetcode.examples import (
    Example,
    ExampleParseError,
    parse_examples,
    parse_inputs,
    sample_mismatches,
)

PRE_LAYOUT = """<p>Do the thing.</p>
<p><strong class="example">Example 1:</strong></p>
<pre><strong>Input:</strong> nums = [2,7,11,15], target = 9
<strong>Output:</strong> [0,1]
<strong>Explanation:</strong> because 2 + 7 == 9.
</pre>
<p><strong class="example">Example 2:</strong></p>
<pre><strong>Input:</strong> nums = [3,3], target = 6
<strong>Output:</strong> [0,1]
</pre>
<p><strong>Constraints:</strong></p>"""

BLOCK_LAYOUT = """<div class="example-block">
<p><strong>Input:</strong> <span class="example-io">s = &quot;a, t = b&quot;, t = &quot;x&quot;</span></p>
<p><strong>Output:</strong> <span class="example-io">false</span></p>
</div>
<div class="example-block">
<p><strong>Input:</strong> <span class="example-io">s = &quot; &quot;, t = &quot;&quot;</span></p>
<p><strong>Output:</strong> <span class="example-io">true</span></p>
</div>"""


def test_pre_layout():
    assert parse_examples(PRE_LAYOUT, ["nums", "target"]) == [
        Example({"nums": [2, 7, 11, 15], "target": 9}, [0, 1]),
        Example({"nums": [3, 3], "target": 6}, [0, 1]),
    ]


def test_block_layout_with_tricky_strings():
    # A string value may contain ", t = " itself; only the real parameter boundary splits.
    assert parse_examples(BLOCK_LAYOUT, ["s", "t"]) == [
        Example({"s": "a, t = b", "t": "x"}, False),
        Example({"s": " ", "t": ""}, True),
    ]


def test_nested_lists_and_empty_output():
    html = "<pre>Input: nums = [0,1,1]\nOutput: []</pre><pre>Input: nums = [0,0,0]\nOutput: [[0,0,0]]</pre>"
    assert [e.output for e in parse_examples(html, ["nums"])] == [[], [[0, 0, 0]]]


def test_errors_are_explicit():
    with pytest.raises(ExampleParseError):
        parse_examples("<p>no examples here</p>", ["n"])
    with pytest.raises(ExampleParseError):
        parse_inputs("n = 3", ["n", "k"])  # a parameter is missing
    with pytest.raises(ExampleParseError):
        parse_inputs("n = three", ["n"])  # not a JSON value


def test_sample_mismatches():
    examples = [Example({"n": 1}, [[1, 2], [3]]), Example({"n": 2}, [])]
    ok = [({"n": 1}, [[3], [2, 1]]), ({"n": 2}, [])]
    assert sample_mismatches(ok, examples, "unordered_nested") == []
    assert sample_mismatches(ok, examples, "exact") == [
        "sample 1: output [[3], [2, 1]] != LeetCode's [[1, 2], [3]]"
    ]
    assert sample_mismatches(ok[:1], examples, "unordered_nested") == [
        "1 samples but LeetCode has 2 examples"
    ]
    assert sample_mismatches([({"n": 9}, [])], examples[1:], "exact") == [
        "sample 1: input {'n': 9} != LeetCode's {'n': 2}"
    ]
