# Spec: Edit Group

## Overview
Step 8 lets a logged-in user edit one of their own groups via a pre-populated
form at `/groups/<id>/edit`. It also introduces the **groups list page** at
`/groups` (currently a stub) — a table that is the natural home for the
per-group "Edit" link (and, in Step 9, "Delete").

The list shows **all groups regardless of owner** (a shared, browsable view),
with an Owner column. Editing, however, remains **owner-scoped**: the "Edit"
action only appears on the current user's own rows, and the edit routes return
404 for groups owned by someone else. Two query helpers are added:
`get_group_by_id` (owner-scoped) and `update_group` (owner-scoped); plus
`get_all_groups` for the list.

## Depends on
- Step 1: Database setup (`groups` table exists)
- Step 3: Login / Logout (`session["user_id"]` is set and enforced)
- Step 7: Add Group (establishes the form pattern, `insert_group`,
  `get_user_groups`)

## Routes
- `GET /groups` — render the groups list (all groups, any owner) — logged-in only
- `GET /groups/<int:id>/edit` — render edit form pre-filled with current values
  — logged-in only
- `POST /groups/<int:id>/edit` — validate and save changes — logged-in only

## Database changes


None. The `groups` table already has `name`, `description`, and
`parent_group_id`.


## Templates
- **Create**: `templates/groups/list.html`
  - Extends `base.html`
  - A table of **all** groups with columns: Name, Owner, Parent, Questions,
    Actions
  - "Owner" shows the owning user's name; "Parent" shows the parent group's
    name, or "—" for a top-level group
  - The Actions cell holds an "Edit" link to `/groups/<id>/edit` **only on the
    current user's own rows** (a "—" placeholder otherwise; Step 9 adds "Delete"
    here for owned rows)
  - An "Add Group" button linking to `/groups/add`
  - Empty state when the user has no groups yet
  - Each row has 5px top and bottom padding
- **Create**: `templates/groups/edit_group.html`
  - Extends `base.html`; mirrors `add_group.html`
  - `method="POST"`, `action="{{ url_for('edit_group', id=group.id) }}"`
  - Fields pre-filled with the group's current values:
    - `name` — text, required, `maxlength="100"`
    - `parent_group_id` — `<select>` of the user's **other** groups (the group
      may not be its own parent), with current parent pre-selected
    - `description` — text, optional, `maxlength="200"`
  - "Save Changes" submit button and a Cancel link back to `/groups`
  - Flash-message block; on validation failure the submitted values are kept

## Files to change
- `database/queries.py`
  - `get_all_groups()` — returns every group (any owner), joined to `users` for
    the owner name and self-joined for the parent name
  - `get_group_by_id(group_id, user_id)` — `SELECT … WHERE id = ? AND
    user_id = ?`; returns the row or `None`
  - `update_group(group_id, user_id, name, parent_group_id, description)` —
    parameterised `UPDATE … WHERE id = ? AND user_id = ?`; returns the number of
    rows changed
- `app.py`
  - Replace the `/groups` stub with a handler that renders `groups/list.html`
    using `get_user_groups`
  - Replace the `/groups/<int:id>/edit` placeholder with a GET + POST handler

## Files to create
- `templates/groups/list.html`
- `templates/groups/edit_group.html`

## New dependencies
None.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- `get_group_by_id` and `update_group` must both scope to
  `id = ? AND user_id = ?` as ownership guards
- Unauthenticated access to any of the routes must redirect to `/login`
- If the group does not exist or belongs to another user, the edit routes
  return **404**
- Validation rules for POST (same as Add Group):
  - `name`: required, non-blank after `strip()`
  - `parent_group_id`: blank → `None`; otherwise must be one of the user's other
    groups; a group may **not** be set as its own parent
  - `description`: optional; `strip()`; store `None` if blank
  - On any validation error, re-render with the message and the **submitted**
    (not original) values pre-filled
- After a successful update, redirect to `url_for("groups")` — do not re-render
- Use CSS variables — never hardcode hex values; no inline styles
- All templates extend `base.html`; all internal links use `url_for()`

## Tests to write
File: `tests/test_edit_group.py`

### Unit tests
| Function | Input | Expected |
|---|---|---|
| `get_all_groups` | — | every group, each with `owner_name` and `parent_name` |
| `get_group_by_id` | valid id, correct `user_id` | matching row |
| `get_group_by_id` | valid id, wrong `user_id` | `None` |
| `get_group_by_id` | non-existent id | `None` |
| `update_group` | valid id, correct `user_id`, new name | row reflects new name; returns 1 |
| `update_group` | valid id, wrong `user_id` | row unchanged; returns 0 |

### Route tests
- `GET /groups` authenticated → 200, lists all groups (including other users');
  another user's group and its owner name appear in the page
- `GET /groups/<id>/edit` unauthenticated → 302 to `/login`
- `GET /groups/<id>/edit` own group → 200, form pre-filled with current values
- `GET /groups/<id>/edit` other user's group → 404
- `GET /groups/<id>/edit` non-existent id → 404
- `POST /groups/<id>/edit` unauthenticated → 302 to `/login`
- `POST /groups/<id>/edit` own group, valid → 302 to `/groups`; DB updated
- `POST /groups/<id>/edit` other user's group → 404
- `POST /groups/<id>/edit` blank name → 200, error message
- `POST /groups/<id>/edit` parent set to itself → 200, error message
- `POST /groups/<id>/edit` blank description → 302; row updated with
  `description = NULL`

## Definition of done
- [ ] `/groups` shows all groups (any owner) in a table with an Owner column;
      an Edit link appears only on the current user's own rows
- [ ] `/groups/<id>/edit` while logged out redirects to `/login`
- [ ] Editing a non-existent or other user's group returns 404
- [ ] The edit form is pre-filled with the group's current values, parent
      pre-selected
- [ ] A group cannot be set as its own parent
- [ ] Submitting valid changes redirects to `/groups` and the row is updated
- [ ] Submitting a blank name re-renders the form with an error and keeps input
- [ ] Submitting without a description stores `description = NULL`
