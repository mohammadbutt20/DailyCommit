# Problems

One folder per problem; the folder name is the slug. Spec: ARCHITECTURE.md §6. Two kinds:

**Local problems**: original content, statement included.

```
<slug>/
  problem.yaml        title, difficulty, topics, function signature, compare mode, limits
  statement.md        what the user sees (Markdown)
  tests.json          [{ "input": {param: value}, "expected": value, "sample": bool }]
  solutions/          ref.py, ref.java, ref.cpp (at least one; ideally all three)
```

**Judge packs** (`leetcode/<slug>/`): make an imported LeetCode problem solvable and judged
here. The slug is LeetCode's (`leetcode.com/problems/<slug>/`). Title, difficulty, topics and
the statement come from `make import-leetcode`, so a pack has no statement.

```
leetcode/<slug>/
  judge.yaml          slug, function, params, returns, compare, limits
  tests.json          same format as above
  solutions/          ref.py, ref.java, ref.cpp (all three required)
```

Match LeetCode's function name and parameter names so the starter code looks familiar.

Rules:

- Never commit statement text: local problems are original (don't copy LeetCode/NeetCode
  statements), and a judge pack has no `statement.md` at all (validation rejects one).
- At least one `sample` test (shown to users) and one hidden test. Hand-write edge cases:
  empty input, single element, duplicates, negatives, bounds.
- Judge packs: the `sample` tests are LeetCode's examples, transcribed. Hidden tests are our own
  edge cases, never copied from LeetCode. Keep them within the problem's stated constraints,
  and make sure each has a single correct answer (or pick a `compare` mode that accepts all).
- `compare`: `exact` (default), `unordered` (top-level list order doesn't matter),
  `unordered_nested` (neither does the order inside each inner list, e.g. 3sum's triplets or
  group-anagrams' groups), or `{ float: 1e-6 }`.
- Types: `int long double bool string`, plus `[]` and `[][]` of each.

Check your work with `make validate-problems`, which also runs every reference solution in the
sandbox. For a judge pack, also run `make check-examples`: it reads LeetCode's examples from the
imported statement (in the database, never the repo) and fails unless the pack's samples are
exactly those examples, in order. Import the problem first (`make import-leetcode LC=<slug>`). Then `make sync-problems` loads changes into the database. A judge pack only loads if
every one of its reference solutions passes; it attaches to the imported LeetCode problem
(importing it first if needed). Only problems that can be judged here are auto-picked as daily
problems.
