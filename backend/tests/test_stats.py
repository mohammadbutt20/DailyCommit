from dailycommit.domain.stats import Stats, SubmissionFact, compute


def fact(problem, verdict="AC", kind="submit", lang="python", difficulty="easy", status="done"):
    return SubmissionFact(problem, kind, status, verdict, lang, difficulty)


def test_no_submissions():
    assert compute([]) == Stats(0, 0, 0, None, {}, {})


def test_rate_counts_judged_submits_and_practice_only():
    facts = [
        fact(1, "AC"),
        fact(1, "WA"),
        fact(2, "AC", kind="practice"),
        fact(3, "TLE", kind="practice"),
        fact(4, "AC", kind="run"),  # samples only: not judged
        fact(5, "IE"),  # our fault: not counted against them
        fact(6, None, status="running"),  # not finished
    ]
    s = compute(facts)
    assert (s.submissions, s.accepted, s.accepted_rate) == (4, 2, 0.5)


def test_problems_solved_are_distinct():
    facts = [fact(1), fact(1), fact(1, lang="java"), fact(2, difficulty="medium"), fact(3, "WA")]
    s = compute(facts)
    assert s.problems_solved == 2
    assert s.by_language == {"java": 1, "python": 2}  # once per language
    assert s.by_difficulty == {"easy": 1, "medium": 1}  # once per problem


def test_a_samples_run_never_counts_as_solved():
    s = compute([fact(1, kind="run"), fact(2, "AC", kind="practice", difficulty="hard")])
    assert (s.problems_solved, s.by_difficulty) == (1, {"hard": 1})
