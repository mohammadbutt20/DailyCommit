import java.util.*;

class Solution {
    public int[][] merge(int[][] intervals) {
        int[][] sorted = intervals.clone();
        Arrays.sort(sorted, (a, b) -> Integer.compare(a[0], b[0]));
        List<int[]> merged = new ArrayList<>();
        for (int[] iv : sorted) {
            int[] last = merged.isEmpty() ? null : merged.get(merged.size() - 1);
            if (last != null && iv[0] <= last[1]) {
                last[1] = Math.max(last[1], iv[1]);
            } else {
                merged.add(new int[] {iv[0], iv[1]});
            }
        }
        return merged.toArray(new int[0][]);
    }
}
