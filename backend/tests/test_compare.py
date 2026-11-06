from dailycommit.sandbox.compare import outputs_match


def test_exact():
    assert outputs_match([[1, 2], [3]], [[1, 2], [3]], "exact")
    assert not outputs_match([1, 2], [2, 1], "exact")
    assert outputs_match("abc", "abc", "exact")
    assert not outputs_match(None, [], "exact")


def test_bool_is_not_int():
    assert not outputs_match(True, 1, "exact")
    assert not outputs_match(0, False, "exact")
    assert outputs_match(False, False, "exact")


def test_int_and_float_compare_numerically():
    assert outputs_match(2.0, 2, "exact")


def test_unordered_top_level():
    assert outputs_match([3, 1, 2], [1, 2, 3], "unordered")
    assert outputs_match([[2, 3], [0, 1]], [[0, 1], [2, 3]], "unordered")
    assert not outputs_match([[3, 2], [0, 1]], [[0, 1], [2, 3]], "unordered")  # inner order kept
    assert not outputs_match([1, 1, 2], [1, 2, 2], "unordered")
    assert not outputs_match(5, [5], "unordered")


def test_float_tolerance():
    mode = {"float": 1e-6}
    assert outputs_match(0.1 + 0.2, 0.3, mode)
    assert outputs_match([1.0000001, 2.0], [1.0, 2.0], mode)
    assert not outputs_match(1.01, 1.0, mode)
    assert outputs_match(1e9 + 1, 1e9, mode)  # relative for large values


def test_unordered_nested_ignores_order_of_groups_and_within_groups():
    expected = [["ate", "eat", "tea"], ["nat", "tan"], ["bat"]]
    assert outputs_match(
        [["bat"], ["tan", "nat"], ["tea", "ate", "eat"]], expected, "unordered_nested"
    )
    assert outputs_match([[-1, 0, 1], [-1, -1, 2]], [[-1, -1, 2], [1, 0, -1]], "unordered_nested")


def test_unordered_nested_still_checks_contents_and_multiplicity():
    assert not outputs_match([["bat"], ["tan"]], [["bat"], ["nat", "tan"]], "unordered_nested")
    assert not outputs_match([[0, 0, 0], [0, 0, 0]], [[0, 0, 0]], "unordered_nested")  # duplicates
    assert not outputs_match([[1, 2]], [[1, 2, 2]], "unordered_nested")
    assert not outputs_match("x", [["x"]], "unordered_nested")
    assert outputs_match([], [], "unordered_nested")


def test_plain_unordered_still_cares_about_inner_order():
    assert not outputs_match([["tan", "nat"]], [["nat", "tan"]], "unordered")
