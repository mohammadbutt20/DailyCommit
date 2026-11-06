class Solution {
public:
    bool isPalindrome(string s) {
        int i = 0, j = (int)s.size() - 1;
        while (i < j) {
            unsigned char a = s[i], b = s[j];
            if (!isalnum(a)) {
                i++;
            } else if (!isalnum(b)) {
                j--;
            } else if (tolower(a) != tolower(b)) {
                return false;
            } else {
                i++;
                j--;
            }
        }
        return true;
    }
};
