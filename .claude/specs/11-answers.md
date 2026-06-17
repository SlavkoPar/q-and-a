# Spec: Answers and Answer

> Status: implemented (2026-06-15). Notes on how it was built vs. this draft:
> - Tables created as `answers` and `question_answers` (SQL name; spec wrote
>   "question-answers" which isn't a valid identifier). `num_of_assigned_answers`
>   column added to `questions` and kept in sync by the query helpers.
> - `/answers` list page filters by name (server-side `q` + a `<datalist>`
>   autocomplete). Add is a page (`add_answer.html`); **Edit uses a modal**
>   (60%×80%, scroll preserved) and **Delete is inline `confirm()`** — so
>   `edit_answer.html` / `delete_answer.html` were intentionally not created
>   (same pattern as groups/questions).
> - Assignment lives on the **group edit page**: each question row shows its
>   assigned-answer count and an "Assigned answers" modal to add (from
>   unassigned, with autocomplete filter) / remove. Routes:
>   `POST /questions/<qid>/answers/assign` and
>   `POST /questions/<qid>/answers/<aid>/unassign`.
> - Global `.form-input` padding set to `0.125rem 0.875rem` per the spec; answer
>   rows get a distinct style (accent-2 colours, 0.1rem row padding).
> - Tests: `tests/test_answers.py`.

## Overview

## Depends on
- Step 1: Database setup (schema must exist)
- Step 2: Registration (user accounts must be creatable)
- Step 3: Login + Logout (session must be set; `/answers` must be a protected route)

## Routes
- GET /answers — render the answers list page

## Database changes

## Create table
### answers

| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | Primary key, autoincrement |
| user_id | INTEGER | Foreign key → users.id, not null |
| short_desc | TEXT | Not null |
| description | TEXT | Nullable |
| link | TEXT | Nullable |
| created_at | TEXT | Default datetime('now') |

### question-answers

| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | Primary key, autoincrement |
| question_id | INTEGER | Foreign key → questions.id, not null |
| answer_id | INTEGER | Foreign key → answers.id, not null |
| future | TEXT | Nullable |
| user_id | INTEGER | Foreign key → users.id, not null |
| created_at | TEXT | Default datetime('now') |




## 12. Expected Behavior


## Templates


- Create templates for answers 
   -- `templates/answers/list.html`
   -- `templates/answers/add_answer.html`
   -- `templates/answers/edit_answer.html`
   -- `templates/answers/delete_answer.html`

## Files to change
- `app.py` 
- `database\queries.py`

## Files to create
   - `templates/answers/list.html`
   - `templates/answers/add_answer.html`
   - `templates/answers/edit_answer.html`
   - `templates/answers/delete_answer.html`



## New dependencies
No new dependencies. 

### Answers list page (the tree) — `templates/answers/list.html`
- filter answers by name


## Rules for implementation

- **Modify**: `templates/base.html` — add an "Answers" navbar link, visible only when `session.user_id` is set


- import rows from `database/import/answers.json` and `database/import/question_answers.json`

- add field number of `assigned answers` in table `questions`
- for question row display number of assigned answers
- create section `Assigned answers' in question form
- create modal for selections of answers which are not already assigned, Modal width: 50% height: 70%


- for answers, and aswers in modal for selection of unassigned answers,  enable autocomplete filter by name
- put link answers in 'base' html
- for answers, set top and bottom paddings to: 3px 
- give different css styles (background, color, borders, filters) for groups, questions, answers
- give the same css styles for assigned-answers as for answers
- set top and bottom paddings to 0.1rem for all answer, question and answer rows
- set styles:
   .form-input { padding: 0.125rem 0.875rem; }


-- Open Modal when click od "Edit Answer" 
-- Modal width: 60% height: 80%
-- keep vertical scroll position after update


## Definition of done
- [ ] Visiting `/answers` without being logged in redirects to `/login`
