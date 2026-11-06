class Solution:
    def trap(self, height: list[int]) -> int:
        i, j = 0, len(height) - 1
        left_max = right_max = water = 0
        while i < j:
            if height[i] < height[j]:
                left_max = max(left_max, height[i])
                water += left_max - height[i]
                i += 1
            else:
                right_max = max(right_max, height[j])
                water += right_max - height[j]
                j -= 1
        return water
