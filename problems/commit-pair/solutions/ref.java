import java.util.*;

class Solution {
    public int[] commitPair(int[] counts, int target) {
        Map<Long, Integer> seen = new HashMap<>();
        for (int i = 0; i < counts.length; i++) {
            Integer j = seen.get((long) target - counts[i]);
            if (j != null) return new int[] {j, i};
            seen.put((long) counts[i], i);
        }
        return new int[0];
    }
}
