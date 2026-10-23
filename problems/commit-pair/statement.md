Your group logged a list of commits, where `counts[i]` is the number of lines changed in
commit `i`. A reviewer wants to look at **exactly two different commits** whose line counts add
up to `target`.

Return the indices of those two commits, in any order. Every input has exactly one valid pair.

**Constraints**

- `2 <= counts.length <= 10^5`
- `-10^9 <= counts[i], target <= 10^9`

Aim for better than checking every pair.
