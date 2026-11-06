class Solution {
public:
    int climbStairs(int n) {
        long long a = 1, b = 1;
        for (int i = 0; i < n; i++) {
            long long next = a + b;
            a = b;
            b = next;
        }
        return (int)a;
    }
};
