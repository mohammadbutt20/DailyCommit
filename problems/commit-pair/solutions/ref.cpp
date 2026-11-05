class Solution {
public:
    vector<int> commitPair(vector<int>& counts, int target) {
        unordered_map<long long, int> seen;
        for (int i = 0; i < (int)counts.size(); i++) {
            auto it = seen.find((long long)target - counts[i]);
            if (it != seen.end()) return {it->second, i};
            seen[counts[i]] = i;
        }
        return {};
    }
};
