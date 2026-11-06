import java.util.*;

class Solution {
    public int longestStreak(int[] days) {
        Set<Long> present = new HashSet<>();
        for (int d : days) present.add((long) d);
        int best = 0;
        for (long d : present) {
            if (!present.contains(d - 1)) {
                int length = 1;
                while (present.contains(d + length)) length++;
                best = Math.max(best, length);
            }
        }
        return best;
    }
}
