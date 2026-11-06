import java.util.*;

class Solution {
    public int[][] mergeBlocks(int[][] blocks) {
        int[][] sorted = blocks.clone();
        Arrays.sort(sorted, (a, b) -> a[0] != b[0] ? Integer.compare(a[0], b[0]) : Integer.compare(a[1], b[1]));
        List<int[]> merged = new ArrayList<>();
        for (int[] b : sorted) {
            int[] last = merged.isEmpty() ? null : merged.get(merged.size() - 1);
            if (last != null && b[0] <= last[1]) {
                last[1] = Math.max(last[1], b[1]);
            } else {
                merged.add(new int[] {b[0], b[1]});
            }
        }
        return merged.toArray(new int[0][]);
    }
}
