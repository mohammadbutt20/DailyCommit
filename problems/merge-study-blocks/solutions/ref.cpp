class Solution {
public:
    vector<vector<int>> mergeBlocks(vector<vector<int>>& blocks) {
        vector<vector<int>> sorted = blocks;
        sort(sorted.begin(), sorted.end());
        vector<vector<int>> merged;
        for (auto& b : sorted) {
            if (!merged.empty() && b[0] <= merged.back()[1]) {
                merged.back()[1] = max(merged.back()[1], b[1]);
            } else {
                merged.push_back({b[0], b[1]});
            }
        }
        return merged;
    }
};
