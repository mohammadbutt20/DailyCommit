class Solution {
public:
    vector<int> productExceptSelf(vector<int>& nums) {
        int n = nums.size();
        vector<int> out(n, 1);
        long long prefix = 1;
        for (int i = 0; i < n; i++) {
            out[i] = (int)prefix;
            prefix *= nums[i];
        }
        long long suffix = 1;
        for (int i = n - 1; i >= 0; i--) {
            out[i] = (int)(out[i] * suffix);
            suffix *= nums[i];
        }
        return out;
    }
};
