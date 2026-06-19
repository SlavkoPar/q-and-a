# Spec: Group and Question

## Overview

## Depends on
- Step 1: Database setup (schema must exist)
- Step 2: Registration (user accounts must be creatable)
- Step 3: Login + Logout (session must be set; `/groups` must be a protected route)

## Routes
- GET /groups — render the groups list page

## Database changes

## Create table

### questions

| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | Primary key, autoincrement |
| user_id | INTEGER | Foreign key → users.id, not null |
| group_id | INTEGER | Foreign key → group.id, not null |
| text | TEXT | Not null |
| description | TEXT | Nullable |
| created_at | TEXT | Default datetime('now') |

### groups

| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | Primary key, autoincrement |
| parent_group_id | INTEGER | Foreign key → groups.id |
| user_id | INTEGER | Foreign key → users.id, not null |
| name | TEXT | Not null |
| description | TEXT | Nullable |
| num_of_questions | INTEGER | Default 0 |
| created_at | TEXT | Default datetime('now') |


## 12. Expected Behavior


## Templates
- Create templates for groups 
   -- `templates/groups/list.html`
   -- `templates/groups/add_group.html`
   -- `templates/groups/edit_group.html`
   -- `templates/groups/delete_group.html`


## Files to change
- `app.py` 
- `database\queries.py`

## Files to create
   - `templates/groups/list.html`
   - `templates/groups/add_group.html`
   - `templates/groups/edit_group.html`
   - `templates/groups/delete_group.html`


## New dependencies
No new dependencies. 

### Groups list page (the tree) — `templates/groups/list.html`
- Renders all groups as a **tree** nested by `parent_group_id`, ordered by name.
- Every group item has 5px top/bottom padding.
- Each row shows an expand/collapse toggle when it has child groups.
- On the current user's own rows:
  - a group with **no questions** shows an `add group` link
    (`/groups/add?parent=<id>`, which pre-selects the parent)
  - a group with **no child groups** shows an `add question` link
    (to the group edit page's Questions section)
  - plus `Edit` and `Delete` (owner-scoped, from Steps 8–9)
- The "Groups" navbar link is present (from Step 7's base.html change).
- filter groups by name, and parent group

## Rules for implementation
- import rows from `database/import/groups.json` and `database/import/questions.json`
- group can have many child groups
- for each group row 
   - which has no questions, enable button for adding of child groups, text `add group`
   - enable button for expand and collapse of the child groups
   - which has no child groups, enable button for adding of questions
   - replace `q' with image `/static/Q.png'
- one group can have many questions
- count num_of_questions
- put link groups in base
- filter groups by name
- set top and bottom paddings, for every group item,  to 5px
- in `templates/groups/group_edit.html` implement section `Questions` for maintenance of questions (add, edit, delete)
- make `Questions` section always visible
- put 'Add Question' button to the top of the `Questions` section
- put 'Questions' section inside of group form, before 'Save Changes' button
- for question row display `num_of_Fixed` field with text `clicks to Fixed` 

-- Open Modal when click od "Edit Question" 
-- Modal width: 60% height: 80%
-- keep vertical scroll position after update


## Definition of done
- [ ] Visiting `/groups` without being logged in redirects to `/login`
