# Problems

One folder per problem; the folder name is the slug. Spec: ARCHITECTURE.md §6.

```
<slug>/
  problem.yaml        title, difficulty, topics, function signature, compare mode, limits
  statement.md        what the user sees (Markdown)
  tests.json          [{ "input": {param: value}, "expected": value, "sample": bool }]
  solutions/ref.py    reference solution (ref.java / ref.cpp once those languages land)
```

Rules:

- Original problems only; don't copy LeetCode/NeetCode statements.
- At least one `sample` test (shown to users) and one hidden test. Hand-write edge cases:
  empty input, single element, duplicates, negatives, bounds.
- `compare`: `exact` (default), `unordered` (top-level list order doesn't matter), or
  `{ float: 1e-6 }`.
- Types: `int long double bool string`, plus `[]` and `[][]` of each.

Check your work with `make validate-problems`, which also runs every reference solution in the
sandbox. Then `make sync-problems` loads changes into the database.
