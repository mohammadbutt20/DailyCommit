class Solution {
public:
    bool isValid(string s) {
        vector<char> stack;
        for (char c : s) {
            if (c == '(' || c == '[' || c == '{') {
                stack.push_back(c);
                continue;
            }
            if (stack.empty()) return false;
            char open = stack.back();
            stack.pop_back();
            if ((c == ')' && open != '(') || (c == ']' && open != '[') || (c == '}' && open != '{')) {
                return false;
            }
        }
        return stack.empty();
    }
};
