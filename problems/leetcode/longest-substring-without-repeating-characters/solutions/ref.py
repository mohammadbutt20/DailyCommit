class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        last: dict[str, int] = {}
        best = start = 0
        for i, c in enumerate(s):
            if last.get(c, -1) >= start:
                start = last[c] + 1
            last[c] = i
            best = max(best, i - start + 1)
        return best
