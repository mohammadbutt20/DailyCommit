class Solution {
    public int maxProfit(int[] prices) {
        int best = 0, low = prices[0];
        for (int p : prices) {
            low = Math.min(low, p);
            best = Math.max(best, p - low);
        }
        return best;
    }
}
