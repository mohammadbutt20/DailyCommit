import java.util.*;

class Solution {
    public int[][] threeSum(int[] nums) {
        int[] a = nums.clone();
        Arrays.sort(a);
        List<int[]> out = new ArrayList<>();
        for (int i = 0; i < a.length - 2; i++) {
            if (i > 0 && a[i] == a[i - 1]) continue;
            int lo = i + 1, hi = a.length - 1;
            while (lo < hi) {
                int total = a[i] + a[lo] + a[hi];
                if (total < 0) {
                    lo++;
                } else if (total > 0) {
                    hi--;
                } else {
                    out.add(new int[] {a[i], a[lo], a[hi]});
                    lo++;
                    while (lo < hi && a[lo] == a[lo - 1]) lo++;
                    hi--;
                }
            }
        }
        return out.toArray(new int[0][]);
    }
}
