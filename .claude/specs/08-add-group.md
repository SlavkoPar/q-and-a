# Spec: Add Group

## Overview
Step 7 lets a logged-in user create a new group through a dedicated form at
`/groups/add`. A group is a named container for questions; it may optionally
sit under a parent group, forming a tree. This step upgrades the placeholder
into a GET + POST handler, inserts validated data into the `groups` table, and
redirects to the profile page on success. Query helpers `insert_group` and
`get_user_groups` are added to `database/queries.py`, and an "Add Group" entry
point is added to the profile page.

> Status: implemented. This spec describes the feature as actually built.

## Depends on
- Step 1: Database setup (`groups` table exists with all required columns)
- Step 3: Login / Logout (`session["user_id"]` is set and checked)
- Step 4 / 5: Profile page exists and is the redirect target after saving

## Schema reference
The `groups` table (from Step 1) has exactly these columns — there is **no**
`amount`, `date`, or `category` column:

| Column | Type | Notes |
| --- | --- | --- |
| id | INTEGER | PK, autoincrement |
| parent_group_id | INTEGER | nullable, FK → groups(id) |
| user_id | INTEGER | not null, FK → users(id) |
| name | TEXT | not null |
| description | TEXT | nullable |
| num_of_questions | INTEGER | not null, default 0 |
| created_at | TEXT | default datetime('now') |

## Routes
- `GET /groups/add` — render the add-group form — logged-in only
- `POST /groups/add` — validate and insert the new group — logged-in only

## Database changes
None. The existing `groups` table is sufficient.

## Templates
- **Create**: `templates/groups/add_group.html`
  - Extends `base.html`; reuses the shared `auth-card` / `form-group` styling
  - `method="POST"`, `action="{{ url_for('add_group') }}"`
  - Fields:
    - `name` — text input, required, `maxlength="100"`
    - `parent_group_id` — `<select>` listing the existing groups, with a
      "— None (top-level group) —" default option
    - `description` — text input, optional, `maxlength="200"`
  - "Save group" submit button and a Cancel link back to `/profile`
  - Flash-message block; on validation failure the previously submitted values
    are pre-filled
- **Modify**: `templates/profile.html` — add an "Add Group" button linking to
  `/groups/add`


## Files to change
- `app.py` — GET + POST handler at `/groups/add` (redirect to `/login` when not
  authenticated; on POST validate, call `insert_group`, redirect to `/profile`)
- `database/queries.py` — add `insert_group` and `get_user_groups`
- `templates/profile.html`, `templates/base.html` — add entry points

## Files to create
- `templates/groups/add_group.html`

## New dependencies
None.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Unauthenticated access to both GET and POST must redirect to `/login`
- Validation rules for POST:
  - `name`: required, non-blank after `strip()`
  - `parent_group_id`: blank → `None`; otherwise must be the id of one of the
    current user's own groups, else re-render with an error
  - `description`: optional; `strip()`; store `None` if blank
  - On any validation error, re-render the form with the message and the
    submitted values pre-filled
- After a successful insert, redirect to `url_for("profile")` — do not re-render
- `num_of_questions` and `created_at` are left to their schema defaults
- Use CSS variables — never hardcode hex values; no inline styles
- All templates extend `base.html`; all internal links use `url_for()`
## Questions feature (implemented alongside Add Group)

A `questions` table was added so groups can actually hold questions. A group is
either a **branch** (has child groups) or a **leaf** (holds questions).

### Schema 

`groups.num_of_questions` is kept in sync with the live count by the query
helpers (recounted on every question insert/delete).





### Question routes (`app.py`)
- `POST /groups/<int:id>/questions/add` — owner of the group only; 404 otherwise
- `POST /questions/<int:qid>/edit` — owner of the question only; 404 otherwise
- `POST /questions/<int:qid>/delete` — owner of the question only; 404 otherwise
- All three are POST-only (GET → 405) and redirect back to the group edit page.

### Question query helpers (`database/queries.py`)
`get_questions_for_group`, `get_question_by_id` (owner-scoped),
`insert_question`, `update_question`, `delete_question` — the last three keep
`groups.num_of_questions` in sync.

### Questions tests — `tests/test_questions.py`
Unit (insert/get/update/delete + count sync + ownership) and route tests
(login required, owner 404s, valid add/edit/delete, blank-text rejection,
POST-only 405s, edit page renders the section).

> Note: the spec originally referenced `templates/groups/group_edit.html`; the
> implemented file is `templates/groups/edit_group.html`.

## Tests to write
File: `tests/test_add_group.py`

### Unit tests
| Function | Input | Expected |
|---|---|---|
| `insert_group` | valid `user_id`, `name`, `description`, `parent_group_id=None` | new row exists with those values, `num_of_questions == 0` |

### Route tests
- `GET /groups/add` unauthenticated → 302 to `/login`
- `POST /groups/add` unauthenticated → 302 to `/login`
- `GET /groups/add` authenticated → 200, body contains `<form` with `method="POST"`
- `POST` authenticated, valid (`name`, `description`, `parent_group_id` blank) →
  302 to `/profile`; new row exists for the user
- `POST` authenticated, blank name → 200, error message shown, no insert
- `POST` authenticated, `parent_group_id` not owned by the user → 200, error,
  no insert
- `POST` authenticated, blank description → 302; row stored with
  `description = NULL`

## Definition of done
- [ ] `/groups/add` while logged out redirects to `/login` (GET and POST)
- [ ] `/groups/add` while logged in shows a form with name, parent-group, and
      description fields
- [ ] The parent dropdown lists the current user's existing groups plus a
      "None" option
- [ ] Submitting a valid group redirects to `/profile` and the row is inserted
- [ ] Submitting a blank name re-renders the form with an error and retains input
- [ ] Submitting a parent group the user does not own re-renders with an error
- [ ] Submitting without a description stores `description = NULL` (no error)
- [ ] The profile "Add Group" button and the navbar "Add Group" link both reach
      `/groups/add`
