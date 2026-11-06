class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<long long, int> seen;
        for (int i = 0; i < (int)nums.size(); i++) {
            auto it = seen.find((long long)target - nums[i]);
            if (it != seen.end()) {
                return {it->second, i};
            }
            seen[nums[i]] = i;
        }
        return {};
    }
};
