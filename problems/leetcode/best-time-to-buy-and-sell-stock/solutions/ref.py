class Solution:
    def maxProfit(self, prices: list[int]) -> int:
        best, low = 0, prices[0]
        for p in prices:
            low = min(low, p)
            best = max(best, p - low)
        return best
