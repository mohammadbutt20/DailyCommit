class Solution:
    def dailyTemperatures(self, temperatures: list[int]) -> list[int]:
        out = [0] * len(temperatures)
        stack: list[int] = []  # days still waiting for a warmer one
        for i, t in enumerate(temperatures):
            while stack and temperatures[stack[-1]] < t:
                j = stack.pop()
                out[j] = i - j
            stack.append(i)
        return out
