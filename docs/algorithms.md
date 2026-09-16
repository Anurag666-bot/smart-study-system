# Explainable algorithms

The application keeps ranking and analytics in Python services rather than in templates. Every result is deterministic for a fixed clock and database snapshot.

## Task priority

`studyapp.algorithms.priority_scheduler` returns a score in `[0, 100]` and reason codes. Completed tasks receive `0` and are sorted after active work. Non-overdue work is scored from importance and urgency; overdue work occupies the `70–100` band, which guarantees that an overdue task outranks future work regardless of its label. Ties use due date and a stable identifier. Computing a score is `O(1)` per task and sorting `n` tasks is `O(n log n)`.

## TF-IDF search

The search tokenizer removes stop words and stems terms. Term frequency is normalized by document length and smoothed inverse document frequency is computed once per query term. Inputs with different document/id lengths and negative `top_k` values are rejected. For `n` documents and `q` query terms, the scoring pass is `O(nq)` after tokenization.

## TextRank summary

TextRank splits bounded input into sentences, constructs a cosine-like word-overlap graph, performs at most 30 power iterations, and restores original sentence order for the selected summary. Inputs are limited to 100,000 characters to prevent unbounded quadratic work. With `s` sentences, the graph is `O(s²)` in memory and per iteration.

## Student analytics

`studyapp.services.analytics.get_student_analytics` calculates task completion, attendance percentage, recent session minutes, current consecutive-session streak, goal progress, and subject-level exam averages. Sessions and attendance are limited to a recent configurable window; all queries are filtered by the authenticated user. A current streak ends today by definition, so missing today's study session produces zero rather than an overstated streak.

## Notifications and achievements

`services.notifications` generates deadline and planner reminders using stable deduplication keys. Running the management command repeatedly is safe. `services.achievements` evaluates actual sessions and completed tasks and uses the unique `(user, achievement)` constraint to make awards idempotent. Both services can run from a scheduler without depending on fragile save-signal side effects.

## Attendance targets

`studyapp.services.attendance.calculate_attendance` treats `PRESENT` and `LATE` as attended, counts `ABSENT` in the scheduled denominator, and excludes `EXCUSED` from that denominator while still reporting it. It returns the percentage, the number of additional attended classes needed to reach a target, and the number of additional absences that can be tolerated without falling below that target. Legacy rows without an explicit status use their boolean `is_present` value. Empty histories and targets of `0` are handled without division errors. Attendance uniqueness is scoped to either one general record or one record per subject and day.

## Adaptive planner

`studyapp.services.planner.build_adaptive_plan` considers active enrollments, pending task dates, upcoming exams, recent study-session minutes, exam averages, and overlapping planner events. It assigns 30–60 minute blocks without exceeding the requested daily capacity, caps subject/query work, and returns reason codes such as `deadline-or-exam-imminent`, `weak-exam-performance`, and `low-recent-study-time`. The preview is available at `/planner/adaptive/`; a POST explicitly persists the displayed blocks as `StudyPlan` rows. Day-boundary comparisons are timezone-aware and use the configured local timezone.
