class Solution {
public:
    vector<vector<int>> merge(vector<vector<int>>& intervals) {
        vector<vector<int>> sorted = intervals;
        sort(sorted.begin(), sorted.end());
        vector<vector<int>> merged;
        for (auto& iv : sorted) {
            if (!merged.empty() && iv[0] <= merged.back()[1]) {
                merged.back()[1] = max(merged.back()[1], iv[1]);
            } else {
                merged.push_back({iv[0], iv[1]});
            }
        }
        return merged;
    }
};
