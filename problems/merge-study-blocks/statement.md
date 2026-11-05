Members booked study blocks in a shared room. Each block is `[start, end]` (inclusive hours,
`start <= end`), and the list is in no particular order.

Merge every pair of blocks that overlap **or touch** (for example `[1, 4]` and `[4, 5]` become
`[1, 5]`, but `[1, 2]` and `[3, 4]` stay separate). Return the merged blocks sorted by start.

**Constraints**

- `0 <= blocks.length <= 10^4`
- `0 <= start <= end <= 10^6`
