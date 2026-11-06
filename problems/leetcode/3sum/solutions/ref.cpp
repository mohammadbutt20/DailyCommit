class Solution {
public:
    vector<vector<int>> threeSum(vector<int>& nums) {
        vector<int> a = nums;
        sort(a.begin(), a.end());
        vector<vector<int>> out;
        for (int i = 0; i + 2 < (int)a.size(); i++) {
            if (i > 0 && a[i] == a[i - 1]) continue;
            int lo = i + 1, hi = (int)a.size() - 1;
            while (lo < hi) {
                int total = a[i] + a[lo] + a[hi];
                if (total < 0) {
                    lo++;
                } else if (total > 0) {
                    hi--;
                } else {
                    out.push_back({a[i], a[lo], a[hi]});
                    lo++;
                    while (lo < hi && a[lo] == a[lo - 1]) lo++;
                    hi--;
                }
            }
        }
        return out;
    }
};
