class Solution {
public:
    int longestStreak(vector<int>& days) {
        unordered_set<long long> present(days.begin(), days.end());
        int best = 0;
        for (long long d : present) {
            if (!present.count(d - 1)) {
                int length = 1;
                while (present.count(d + length)) length++;
                best = max(best, length);
            }
        }
        return best;
    }
};
