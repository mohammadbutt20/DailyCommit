class Solution {
public:
    vector<vector<int>> rotateClockwise(vector<vector<int>>& grid) {
        int rows = grid.size();
        int cols = rows == 0 ? 0 : grid[0].size();
        vector<vector<int>> out(cols, vector<int>(rows));
        for (int r = 0; r < rows; r++)
            for (int c = 0; c < cols; c++)
                out[c][rows - 1 - r] = grid[r][c];
        return out;
    }
};
