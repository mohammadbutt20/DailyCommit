class Solution {
public:
    vector<vector<string>> groupAnagrams(vector<string>& strs) {
        unordered_map<string, int> index;
        vector<vector<string>> groups;
        for (const string& s : strs) {
            string key = s;
            sort(key.begin(), key.end());
            auto it = index.find(key);
            if (it == index.end()) {
                index[key] = (int)groups.size();
                groups.push_back({s});
            } else {
                groups[it->second].push_back(s);
            }
        }
        return groups;
    }
};
