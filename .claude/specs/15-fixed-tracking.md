# Spec: Fixed / Not-Fixed tracking

## Overview
The right sidebar (Step 13) lets a user pick a question and cycle through its
assigned answers with **Fixed** / **Not Fixed** buttons — but the outcome is
currently client-only and forgotten on reload. This step **persists** those
outcomes: each click records whether a given answer fixed a given question, so
the app can show which answer resolved a question and how often each answer
works.

## Depends on
- Step 11: answers (questions, answers, question_answers)
- Step 13: sidebar (the Fixed / Not-Fixed flow lives here)

## Routes
- `POST /questions/<int:qid>/answers/<int:aid>/outcome` — record an outcome for
  an (question, answer) pair — logged-in, owner of the question only.
  - form field `outcome` ∈ {`fixed`, `not_fixed`}.
  - returns JSON `{ "ok": true }` (the sidebar calls it via fetch, no reload).

## Database changes

### Create table `resolutions`

| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | Primary key, autoincrement |
| question_id | INTEGER | Foreign key → questions.id, not null |
| answer_id | INTEGER | Foreign key → answers.id, not null |
| user_id | INTEGER | Foreign key → users.id, not null |
| outcome | TEXT | not null; `fixed` or `not_fixed` |
| created_at | TEXT | Default datetime('now') |

No changes to existing tables. (Optionally add `num_of_fixed` to `questions`
later; not required here — counts can be derived.)

## Files to change
- `database/db.py` — add the `resolutions` table in `init_db()`.
- `database/queries.py`
  - `record_outcome(question_id, answer_id, user_id, outcome)` — insert a row.
  - `get_fixed_answer_ids(question_id)` — set/list of answer ids marked `fixed`
    for a question (for display).
- `app.py`
  - `record_outcome_route` at `POST /questions/<qid>/answers/<aid>/outcome`
    (owner-scoped; validate `outcome`; 404 if the question isn't the user's).
  - Include each answer's fixed-state in the sidebar data (`nav_questions`):
    mark assigned answers that have a `fixed` resolution.
- `templates/base.html`
  - `markFixed()` → POST the `fixed` outcome for the current answer
  then show
    "✓ Marked as fixed."
  - `nextAnswer()` → POST the `not_fixed` outcome for the current answer before
    advancing.
  - In the answer card, show a small "✓ fixed before" badge when the current
    answer was previously marked fixed for this question.

## Files to create
None.

## New dependencies
None.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`; parameterised queries.
- The outcome route is owner-scoped (the question must belong to the session
  user) and POST-only; `GET` → 405; unauthenticated → redirect to `/login` (or
  401 for the JSON endpoint — pick one and be consistent).
- `outcome` must be validated against {`fixed`, `not_fixed`}; reject others.
- Recording is **append-only** (a log) — clicking Fixed/Not Fixed multiple times
  just adds rows; "is this answer fixed" = "has any `fixed` row".
- Side-nav JS posts via `fetch` (no navigation); failures fail silently so the
  troubleshooting flow keeps working offline-ish.
- Use CSS variables; no inline styles; reuse existing answer styling.
- in `assigned answer` row, show column `num_of_Fixed`
- in `question` row, put `num_of_Fixed' to the same line with num of assigned answers

## Tests to write
File: `tests/test_resolutions.py`
- `record_outcome` inserts a row; `get_fixed_answer_ids` returns the fixed ones
  and excludes `not_fixed`-only answers.
- `POST .../outcome` with `fixed` → 200/JSON ok; row exists.
- `POST .../outcome` with a bad outcome → 400, no row.
- `POST .../outcome` for another user's question → 404.
- `GET .../outcome` → 405.

## Definition of done
- [ ] Clicking **Fixed** in the sidebar records a `fixed` resolution (survives reload).
- [ ] Clicking **Not Fixed** records a `not_fixed` resolution and advances.
- [ ] An answer previously marked fixed for a question shows a "fixed before" badge.
- [ ] The outcome route is owner-scoped, POST-only, and validates `outcome`.
- [ ] Tests in `tests/test_resolutions.py` pass.
