class Solution {
public:
    int coinChange(vector<int>& coins, int amount) {
        int inf = amount + 1;
        vector<int> dp(amount + 1, inf);
        dp[0] = 0;
        for (int a = 1; a <= amount; a++) {
            for (int c : coins) {
                if (c <= a && dp[a - c] + 1 < dp[a]) dp[a] = dp[a - c] + 1;
            }
        }
        return dp[amount] == inf ? -1 : dp[amount];
    }
};
