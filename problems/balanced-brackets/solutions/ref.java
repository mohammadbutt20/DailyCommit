import java.util.*;

class Solution {
    public boolean isBalanced(String s) {
        Map<Character, Character> pairs = Map.of(')', '(', ']', '[', '}', '{');
        Deque<Character> stack = new ArrayDeque<>();
        for (char ch : s.toCharArray()) {
            Character open = pairs.get(ch);
            if (open != null) {
                if (stack.isEmpty() || !stack.pop().equals(open)) return false;
            } else {
                stack.push(ch);
            }
        }
        return stack.isEmpty();
    }
}
