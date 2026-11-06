class Solution {
    public int[][] rotateClockwise(int[][] grid) {
        int rows = grid.length;
        int cols = rows == 0 ? 0 : grid[0].length;
        int[][] out = new int[cols][rows];
        for (int r = 0; r < rows; r++)
            for (int c = 0; c < cols; c++)
                out[c][rows - 1 - r] = grid[r][c];
        return out;
    }
}
