class Solution:
    def commitPair(self, counts: list[int], target: int) -> list[int]:
        seen: dict[int, int] = {}
        for i, c in enumerate(counts):
            if target - c in seen:
                return [seen[target - c], i]
            seen[c] = i
        return []
