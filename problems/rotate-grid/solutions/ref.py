class Solution:
    def rotateClockwise(self, grid: list[list[int]]) -> list[list[int]]:
        return [list(row) for row in zip(*grid[::-1])]
