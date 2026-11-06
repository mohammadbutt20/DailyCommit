class Solution {
public:
    int maxProfit(vector<int>& prices) {
        int best = 0, low = prices[0];
        for (int p : prices) {
            low = min(low, p);
            best = max(best, p - low);
        }
        return best;
    }
};
