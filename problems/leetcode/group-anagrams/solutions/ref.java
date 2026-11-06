import java.util.*;

class Solution {
    public String[][] groupAnagrams(String[] strs) {
        Map<String, List<String>> groups = new LinkedHashMap<>();
        for (String s : strs) {
            char[] key = s.toCharArray();
            Arrays.sort(key);
            groups.computeIfAbsent(new String(key), k -> new ArrayList<>()).add(s);
        }
        String[][] out = new String[groups.size()][];
        int i = 0;
        for (List<String> g : groups.values()) out[i++] = g.toArray(new String[0]);
        return out;
    }
}
