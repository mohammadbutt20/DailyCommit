class Solution {
    public String minWindow(String s, String t) {
        int[] need = new int[128];
        for (char c : t.toCharArray()) need[c]++;
        int missing = t.length(), start = 0, bestStart = 0, bestLen = Integer.MAX_VALUE;
        for (int end = 0; end < s.length(); end++) {
            if (need[s.charAt(end)]-- > 0) missing--;
            while (missing == 0) {
                if (end - start + 1 < bestLen) {
                    bestLen = end - start + 1;
                    bestStart = start;
                }
                if (++need[s.charAt(start++)] > 0) missing++;
            }
        }
        return bestLen == Integer.MAX_VALUE ? "" : s.substring(bestStart, bestStart + bestLen);
    }
}
