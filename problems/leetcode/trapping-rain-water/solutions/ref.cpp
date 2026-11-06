class Solution {
public:
    int trap(vector<int>& height) {
        int i = 0, j = (int)height.size() - 1, leftMax = 0, rightMax = 0;
        long long water = 0;
        while (i < j) {
            if (height[i] < height[j]) {
                leftMax = max(leftMax, height[i]);
                water += leftMax - height[i];
                i++;
            } else {
                rightMax = max(rightMax, height[j]);
                water += rightMax - height[j];
                j--;
            }
        }
        return (int)water;
    }
};
