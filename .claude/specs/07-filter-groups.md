# Spec: Filter Groups (by name and parent)

> Status: implemented.

## Overview
Step 10 adds filtering to the groups list page. Two query-string parameters on
`GET /groups` drive it:
- `q` — case-insensitive substring match on the group name
- `parent` — a group id; show only groups whose `parent_group_id` equals it

When neither is present, the page shows the full **tree** (as built in the
groups feature). When either is present, the page shows a **flat list** of the
matching groups (a filtered tree is confusing), with a parent column. The filter
bar stays populated so the active filter is visible, and a "Clear" link resets
it. The list shows all groups (any owner); Edit/Delete remain owner-scoped.

## Depends on
- Step 1: Database setup (`groups` table exists)
- Step 3: Login / Logout (`session["user_id"]` is set and enforced)
- Groups feature (the `/groups` list page and `get_all_groups` exist)

## Routes
No new routes. `GET /groups` reads optional `q` and `parent` query parameters.

## Database changes
None.

## Templates
- **Modify**: `templates/groups/list.html`
  - A `GET` filter bar above the list: a `q` text input (pre-filled), a `parent`
    `<select>` listing all groups ("Any parent group" default, current selection
    kept), an "Apply" button, and a "Clear" link shown only when a filter is
    active. Both controls have `aria-label`s.
  - When a filter is active, render a flat `render_flat` list (name, owner,
    parent, question count, owner-scoped Edit/Delete); empty state:
    "No groups match this filter." Otherwise render the tree as before.

## Files to change
- `app.py` — in `groups()`, read `q`/`parent` from `request.args`, compute
  `filter_active`, query `get_all_groups(q, parent_id)`, and pass the flat list
  (or tree), the active values, and the parent dropdown options to the template
- `database/queries.py` — `get_all_groups(q=None, parent_id=None)`: build a
  parameterised `WHERE` (`name LIKE ?` for `q`, `parent_group_id = ?` for
  `parent_id`); no filter ⇒ all groups
- `templates/groups/list.html` — filter bar + flat view
- `static/css/style.css` — `.groups-filter` and `.tree-parent` styles

## Files to create
None.

## New dependencies
None.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — pass the `%q%` pattern and the parent id as `?`
  parameters; never string-format values into SQL (the static `WHERE`-clause
  fragments are assembled in Python but carry no values)
- A blank/whitespace `q` and a non-numeric `parent` are treated as no filter
- The filter form uses `method="GET"` so filters are shareable/bookmarkable
- Build the form `action` and the "Clear" link with `url_for("groups")`
- Use CSS variables — never hardcode hex values; no inline styles (except the
  allowed `display:inline` on the delete `<form>`)

## Tests to write
File: `tests/test_filter_groups.py`

### Unit tests (`get_all_groups`)
| Input | Expected |
|---|---|
| `q=None, parent_id=None` | all groups |
| `q="alph"` | only name matches (case-insensitive) |
| `parent_id=<id>` | only that parent's direct children |
| `q="<no match>"` | empty list |

### Route tests
- `GET /groups?q=<term>` → 200; matching rows shown, non-matches absent from the
  list (they may still appear as dropdown `<option>`s)
- `GET /groups?parent=<id>` → 200; only that parent's children listed
- `GET /groups?q=<no match>` → 200; "No groups match this filter."
- `GET /groups` (no params) → 200; full tree

## Definition of done
- [ ] `/groups` with no params shows the full tree (unchanged)
- [ ] Filtering by name narrows the list, case-insensitive
- [ ] Filtering by parent group shows only that parent's children
- [ ] Name + parent combine (children of the parent whose name also matches)
- [ ] The filter controls stay populated; "Clear" resets them
- [ ] No matches shows a message, not an error

## Future work (out of scope)
Questions are group-scoped (a question belongs to a group; managed in the group
edit page) — see `09-groups-with-questions.md`. The next content feature is
**answers** (`14-answers.md`): an `answers` table plus a `question-answers`
join, with answers assigned to questions.
