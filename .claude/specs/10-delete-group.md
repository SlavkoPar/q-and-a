# Spec: Delete Group

## Overview
Step 9 lets a logged-in user permanently delete one of their own groups from
the groups list page. A "Delete" button per row submits a POST to
`/groups/<id>/delete`; the handler verifies ownership, removes the row, and
redirects back to `/groups`. There is no separate confirmation page — a
browser-side `confirm()` dialog guards against accidental deletion. The
`get_group_by_id` helper from Step 8 is reused for ownership verification; only
a new `delete_group` mutation helper is added.

Because groups form a tree (`parent_group_id` → `groups.id`), deleting a group
that still has **child groups** would orphan or break those references. This
step therefore refuses to delete a group that has children: the user must remove
or re-parent the children first.

## Depends on
- Step 1: Database setup (`groups` table exists)
- Step 3: Login / Logout (`session["user_id"]` is set and enforced)
- Step 8: Edit Group (`get_group_by_id` exists; the groups list page exists with
  an Actions column)

## Routes
- `POST /groups/<int:id>/delete` — verify ownership, delete the group, redirect
  to `/groups` — logged-in only

## Database changes
None.

## Templates
- **Modify**: `templates/groups/list.html`
  - In the existing Actions cell per row, add a delete form:
    ```html
    <form method="POST" action="{{ url_for('delete_group_route', id=group.id) }}"
          style="display:inline"
          onsubmit="return confirm('Delete this group?')">
      <button type="submit" class="btn-delete">Delete</button>
    </form>
    ```
  - The delete button only appears on the current user's own rows (delete is
    owner-scoped).
  - `style="display:inline"` on the `<form>` is the one allowed inline style
    (a layout utility, not a design value). No hex colours may be inlined.
  - Note: the route's view function is `delete_group_route` (the name
    `delete_group` is the query helper), so `url_for('delete_group_route', …)`.

## Files to change
- `database/queries.py`
  - `delete_group(group_id, user_id)` — parameterised
    `DELETE FROM groups WHERE id = ? AND user_id = ?`; commits, closes, returns
    the number of rows deleted
  - `count_child_groups(group_id, user_id)` — returns how many groups have this
    group as their `parent_group_id` (used to block deletion of non-empty
    parents)
- `app.py`
  - POST-only handler at `/groups/<int:id>/delete`:
    - redirect to `/login` if not authenticated
    - `get_group_by_id(id, user_id)`; if `None`, abort 404
    - if `count_child_groups(id, user_id) > 0`, flash an error and redirect to
      `/groups` without deleting
    - otherwise `delete_group(id, user_id)` and redirect to `/groups`
- `templates/groups/list.html` — add the delete form per row
- `static/css/style.css` — add a `.btn-delete` style using the existing
  `--danger` CSS variable

## Files to create
None.

## New dependencies
None.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- `delete_group` must scope its `DELETE` to `id = ? AND user_id = ?`
- The route accepts `POST` only — a bare `GET` must return **405**
- Unauthenticated access must redirect to `/login` (302)
- A non-existent or other user's group must return **404**
- A group that still has child groups must **not** be deleted; flash an error
  and redirect to `/groups`
- After a successful delete, redirect to `url_for("groups")` — do not render
- Use CSS variables — never hardcode hex values
- No inline styles except the allowed `display:inline` on the delete `<form>`

## Tests to write
File: `tests/test_delete_group.py`

### Unit tests
| Function | Input | Expected |
|---|---|---|
| `delete_group` | valid id, correct `user_id` | row removed; returns 1 |
| `delete_group` | valid id, wrong `user_id` | row remains; returns 0 |
| `delete_group` | non-existent id | no error; returns 0 |
| `count_child_groups` | parent with N children | returns N |

### Route tests
- `POST /groups/<id>/delete` unauthenticated → 302 to `/login`
- `POST /groups/<id>/delete` own childless group → 302 to `/groups`; row gone
- `POST /groups/<id>/delete` own group **with children** → 302 to `/groups`,
  flash error, row still present
- `POST /groups/<id>/delete` other user's group → 404; row still present
- `POST /groups/<id>/delete` non-existent id → 404
- `GET /groups/<id>/delete` → 405

## Definition of done
- [ ] `POST /groups/<id>/delete` while logged out redirects to `/login`
- [ ] Deleting a non-existent or other user's group returns 404
- [ ] `GET`ing the delete URL returns 405
- [ ] Deleting a group with child groups is refused with a flash message
- [ ] Confirming the dialog deletes a childless group and redirects to `/groups`,
      where it no longer appears
- [ ] Cancelling the `confirm()` dialog leaves the group intact
- [ ] Each list row shows both "Edit" and "Delete" actions
