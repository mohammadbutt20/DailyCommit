"""The demo's wrong attempts: real buggy or brute-force solutions, with the results our judge
really gives them (as `judge_submission` runs a submit). The seed stores these as the members'
failed tries before an Accepted. Tests re-judge every attempt and require exactly these
results, so the demo never shows a verdict our judge wouldn't give:
WA attempts in tests/test_seed.py (make test), TLE attempts in the sandbox suite.

`results` has one letter per test, in submit order (samples first): A accepted, W wrong
answer, T time limit, s skipped (a failed sample stops the hidden tests; a TLE ends the run).
`sample_outputs` are the values returned on sample tests that were wrong (shown on the
submission's "failed example").
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Attempt:
    slug: str
    verdict: str
    results: str
    code: str
    sample_outputs: dict[int, Any] = field(default_factory=dict)


ATTEMPTS: dict[str, Attempt] = {
    # Profit as max - min, ignoring that you must buy before you sell.
    "best_time_max_minus_min": Attempt(
        slug="best-time-to-buy-and-sell-stock",
        verdict="WA",
        results="WWsssssssss",
        sample_outputs={0: 6, 1: 6},
        code="""class Solution:
    def maxProfit(self, prices: list[int]) -> int:
        return max(prices) - min(prices)
""",
    ),
    # Compares neighbours without sorting first.
    "contains_duplicate_neighbours": Attempt(
        slug="contains-duplicate",
        verdict="WA",
        results="WAAssssssss",
        sample_outputs={0: False},
        code="""class Solution:
    def containsDuplicate(self, nums: list[int]) -> bool:
        return any(nums[i] == nums[i + 1] for i in range(len(nums) - 1))
""",
    ),
    # Compares the sets of letters, so letter counts are ignored.
    "valid_anagram_sets": Attempt(
        slug="valid-anagram",
        verdict="WA",
        results="AAAAAWAAAW",
        code="""class Solution:
    def isAnagram(self, s: str, t: str) -> bool:
        return set(s) == set(t)
""",
    ),
    # Fibonacci, off by one.
    "climbing_stairs_off_by_one": Attempt(
        slug="climbing-stairs",
        verdict="WA",
        results="WWsssssss",
        sample_outputs={0: 1, 1: 2},
        code="""class Solution:
    def climbStairs(self, n: int) -> int:
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a
""",
    ),
    # Division by each element; a single zero is handled wrong.
    "product_by_division": Attempt(
        slug="product-of-array-except-self",
        verdict="WA",
        results="AWssssssss",
        sample_outputs={1: [0, 0, 0, 0, 0]},
        code="""class Solution:
    def productExceptSelf(self, nums: list[int]) -> list[int]:
        total = 1
        for x in nums:
            total *= x
        return [total // x if x else 0 for x in nums]
""",
    ),
    # Plain binary search, as if the array weren't rotated.
    "rotated_plain_binary_search": Attempt(
        slug="search-in-rotated-sorted-array",
        verdict="WA",
        results="WAAssssssssssss",
        sample_outputs={0: -1},
        code="""class Solution:
    def search(self, nums: list[int], target: int) -> int:
        lo, hi = 0, len(nums) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if nums[mid] == target:
                return mid
            if nums[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1
""",
    ),
    # Right answers, O(n^3): times out on the large hidden test.
    "three_sum_brute_force": Attempt(
        slug="3sum",
        verdict="TLE",
        results="AAAAAAAAAAT",
        code="""class Solution:
    def threeSum(self, nums: list[int]) -> list[list[int]]:
        found = set()
        n = len(nums)
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    if nums[i] + nums[j] + nums[k] == 0:
                        found.add(tuple(sorted((nums[i], nums[j], nums[k]))))
        return [list(t) for t in found]
""",
    ),
    # Right answers, O(n^2): times out on the large hidden test.
    "trapping_rain_water_quadratic": Attempt(
        slug="trapping-rain-water",
        verdict="TLE",
        results="AAAAAAAAAAT",
        code="""class Solution:
    def trap(self, height: list[int]) -> int:
        water = 0
        for i in range(len(height)):
            water += min(max(height[: i + 1]), max(height[i:])) - height[i]
        return water
""",
    ),
}
