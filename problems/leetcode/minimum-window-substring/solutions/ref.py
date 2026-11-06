from collections import Counter


class Solution:
    def minWindow(self, s: str, t: str) -> str:
        need = Counter(t)
        missing = len(t)
        start = best_start = 0
        best_len = len(s) + 1
        for end, c in enumerate(s, 1):
            if need[c] > 0:
                missing -= 1
            need[c] -= 1
            if missing == 0:
                while need[s[start]] < 0:
                    need[s[start]] += 1
                    start += 1
                if end - start < best_len:
                    best_start, best_len = start, end - start
                need[s[start]] += 1
                missing += 1
                start += 1
        return "" if best_len > len(s) else s[best_start : best_start + best_len]
