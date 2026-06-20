"""Pure data-access helpers for the profile page.

No Flask imports here — each function opens a connection via get_db(),
runs a parameterised query, and closes the connection before returning.

Note: this app is the Q&A tool (users + groups). There is no expenses
table, so the profile's summary stats are derived from the user's groups
and question counts rather than spending.
"""

import re
from datetime import datetime

from database.db import get_db


def _format_member_since(created_at):
    """Format a stored 'YYYY-MM-DD HH:MM:SS' timestamp as 'Month YYYY'."""
    if not created_at:
        return ""
    parsed = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
    return parsed.strftime("%B %Y")


def get_user_by_id(user_id):
    """Return {name, email, member_since} for user_id, or None if absent."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": _format_member_since(row["created_at"]),
    }


def get_summary_stats(user_id):
    """Return the user's profile stats derived from their groups.

    {groups: int, questions: int, answers: int}

    'answers' is always 0 for now — the schema tracks question counts on
    groups but has no answers table yet. Users with no groups get zeros
    rather than an error.
    """
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS groups,
                   COALESCE(SUM(num_of_questions), 0) AS questions
            FROM groups
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        answers = conn.execute(
            "SELECT COUNT(*) AS n FROM answers WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"]
    finally:
        conn.close()

    return {
        "groups": row["groups"],
        "questions": row["questions"],
        "answers": answers,
    }


# ------------------------------------------------------------------ #
# Groups                                                             #
# ------------------------------------------------------------------ #

def get_user_groups(user_id):
    """Return [{id, name}] of the user's groups, ordered by name."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, name FROM groups WHERE user_id = ? ORDER BY name",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


def get_all_groups(q=None, parent_id=None):
    """Return groups (any owner) with owner + parent names, optionally filtered.

    q: case-insensitive substring on the group name.
    parent_id: only groups whose parent_group_id equals this value.
    """
    clauses = []
    params = []
    if q:
        clauses.append("g.name LIKE ?")
        params.append(f"%{q}%")
    if parent_id is not None:
        clauses.append("g.parent_group_id = ?")
        params.append(parent_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT g.id, g.name, g.description, g.num_of_questions,
                   g.user_id, g.parent_group_id,
                   u.name AS owner_name,
                   p.name AS parent_name
            FROM groups g
            JOIN users u ON u.id = g.user_id
            LEFT JOIN groups p ON p.id = g.parent_group_id
            {where}
            ORDER BY g.name
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_group_by_id(group_id, user_id):
    """Return the group row only if it belongs to user_id, else None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM groups WHERE id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def insert_group(user_id, name, parent_group_id=None, description=None):
    """Insert a new group and return its id (defaults fill the rest)."""
    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO groups (user_id, parent_group_id, name, description)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, parent_group_id, name, description),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_group(group_id, user_id, name, parent_group_id=None, description=None):
    """Update a group in place, scoped to id AND user_id. Returns rows changed."""
    conn = get_db()
    try:
        cur = conn.execute(
            """
            UPDATE groups
               SET name = ?, parent_group_id = ?, description = ?
             WHERE id = ? AND user_id = ?
            """,
            (name, parent_group_id, description, group_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def count_child_groups(group_id, user_id):
    """How many of the user's groups have this group as their parent."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM groups "
            "WHERE parent_group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return row["n"]


def delete_group(group_id, user_id):
    """Delete a group scoped to id AND user_id. Returns rows deleted."""
    conn = get_db()
    try:
        cur = conn.execute(
            "DELETE FROM groups WHERE id = ? AND user_id = ?",
            (group_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Questions                                                          #
# ------------------------------------------------------------------ #

def _recount_group_questions(conn, group_id):
    """Sync groups.num_of_questions to the live count. Uses an open conn."""
    conn.execute(
        """
        UPDATE groups
           SET num_of_questions = (
               SELECT COUNT(*) FROM questions WHERE group_id = ?
           )
         WHERE id = ?
        """,
        (group_id, group_id),
    )


def get_questions_for_group(group_id):
    """Return [{id, text, description, created_at}] for a group, oldest first."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT id, text, description, created_at
            FROM questions
            WHERE group_id = ?
            ORDER BY created_at, id
            """,
            (group_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_question_by_id(question_id, user_id):
    """Return the question row only if it belongs to user_id, else None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM questions WHERE id = ? AND user_id = ?",
            (question_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def insert_question(group_id, user_id, text, description=None):
    """Insert a question and keep the group's num_of_questions in sync."""
    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO questions (group_id, user_id, text, description)
            VALUES (?, ?, ?, ?)
            """,
            (group_id, user_id, text, description),
        )
        _recount_group_questions(conn, group_id)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_question(question_id, user_id, text, description=None):
    """Update a question's text/description, scoped to owner. Returns rows changed."""
    conn = get_db()
    try:
        cur = conn.execute(
            """
            UPDATE questions
               SET text = ?, description = ?
             WHERE id = ? AND user_id = ?
            """,
            (text, description, question_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_question(question_id, user_id):
    """Delete a question (owner-scoped) and re-sync the group's count."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT group_id FROM questions WHERE id = ? AND user_id = ?",
            (question_id, user_id),
        ).fetchone()
        if row is None:
            return 0
        cur = conn.execute(
            "DELETE FROM questions WHERE id = ? AND user_id = ?",
            (question_id, user_id),
        )
        _recount_group_questions(conn, row["group_id"])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Answers                                                            #
# ------------------------------------------------------------------ #

def get_all_answers(q=None):
    """Return answers (any owner), optionally filtered by short_desc substring."""
    clauses = []
    params = []
    if q:
        clauses.append("a.short_desc LIKE ?")
        params.append(f"%{q}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT a.id, a.user_id, a.short_desc, a.description, a.link,
                   a.created_at, u.name AS owner_name
            FROM answers a
            JOIN users u ON u.id = a.user_id
            {where}
            ORDER BY a.short_desc
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_answer_by_id(answer_id, user_id):
    """Return the answer row only if it belongs to user_id, else None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM answers WHERE id = ? AND user_id = ?",
            (answer_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def insert_answer(user_id, short_desc, description=None, link=None):
    """Insert an answer; return the new id."""
    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO answers (user_id, short_desc, description, link)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, short_desc, description, link),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_answer(answer_id, user_id, short_desc, description=None, link=None):
    """Update an answer, scoped to owner. Returns rows changed."""
    conn = get_db()
    try:
        cur = conn.execute(
            """
            UPDATE answers
               SET short_desc = ?, description = ?, link = ?
             WHERE id = ? AND user_id = ?
            """,
            (short_desc, description, link, answer_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_answer(answer_id, user_id):
    """Delete an answer (owner-scoped) and its question links; re-sync counts."""
    conn = get_db()
    try:
        if conn.execute(
            "SELECT 1 FROM answers WHERE id = ? AND user_id = ?",
            (answer_id, user_id),
        ).fetchone() is None:
            return 0
        affected = [
            r["question_id"]
            for r in conn.execute(
                "SELECT question_id FROM question_answers WHERE answer_id = ?",
                (answer_id,),
            ).fetchall()
        ]
        conn.execute("DELETE FROM question_answers WHERE answer_id = ?", (answer_id,))
        cur = conn.execute(
            "DELETE FROM answers WHERE id = ? AND user_id = ?",
            (answer_id, user_id),
        )
        for qid in set(affected):
            _recount_question_answers(conn, qid)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Question ↔ Answer assignments                                      #
# ------------------------------------------------------------------ #

def _recount_question_answers(conn, question_id):
    """Sync questions.num_of_assigned_answers to the live link count."""
    conn.execute(
        """
        UPDATE questions
           SET num_of_assigned_answers = (
               SELECT COUNT(*) FROM question_answers WHERE question_id = ?
           )
         WHERE id = ?
        """,
        (question_id, question_id),
    )


def get_assigned_answers(question_id):
    """Return the answers assigned to a question, ordered by short_desc."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT a.id, a.short_desc, a.description, a.link,
                   qa.num_of_Fixed AS num_of_fixed
            FROM question_answers qa
            JOIN answers a ON a.id = qa.answer_id
            WHERE qa.question_id = ?
            ORDER BY a.short_desc
            """,
            (question_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_unassigned_answers(question_id):
    """Return answers not yet assigned to the given question."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT a.id, a.short_desc, a.description, a.link
            FROM answers a
            WHERE a.id NOT IN (
                SELECT answer_id FROM question_answers WHERE question_id = ?
            )
            ORDER BY a.short_desc
            """,
            (question_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def assign_answer(question_id, answer_id, user_id):
    """Link an answer to a question (no-op if already linked). True if added."""
    conn = get_db()
    try:
        if conn.execute(
            "SELECT 1 FROM question_answers WHERE question_id = ? AND answer_id = ?",
            (question_id, answer_id),
        ).fetchone() is not None:
            return False
        conn.execute(
            "INSERT INTO question_answers (question_id, answer_id, user_id) "
            "VALUES (?, ?, ?)",
            (question_id, answer_id, user_id),
        )
        _recount_question_answers(conn, question_id)
        conn.commit()
        return True
    finally:
        conn.close()


def unassign_answer(question_id, answer_id):
    """Remove an answer↔question link and re-sync the count. Rows deleted."""
    conn = get_db()
    try:
        cur = conn.execute(
            "DELETE FROM question_answers WHERE question_id = ? AND answer_id = ?",
            (question_id, answer_id),
        )
        _recount_question_answers(conn, question_id)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_user_questions(user_id):
    """Return [{id, text, group_id}] of the user's questions, ordered by text.

    Used to populate the global side-navigation question list.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, text, group_id FROM questions WHERE user_id = ? ORDER BY text",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


# ------------------------------------------------------------------ #
# Resolutions (Fixed / Not-Fixed outcomes)                           #
# ------------------------------------------------------------------ #

def record_outcome(question_id, answer_id, user_id, outcome):
    """Append a resolution log row (outcome is 'fixed' or 'not_fixed')."""
    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO resolutions (question_id, answer_id, user_id, outcome)
            VALUES (?, ?, ?, ?)
            """,
            (question_id, answer_id, user_id, outcome),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_fixed_answer_ids(question_id):
    """Return the set of answer ids marked 'fixed' for a question."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT answer_id FROM resolutions "
            "WHERE question_id = ? AND outcome = 'fixed'",
            (question_id,),
        ).fetchall()
    finally:
        conn.close()
    return {row["answer_id"] for row in rows}


def increment_fixed(question_id, answer_id):
    """Bump num_of_Fixed on the (question, answer) link. Returns rows changed
    (0 if the answer is not assigned to the question)."""
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE question_answers "
            "SET num_of_Fixed = COALESCE(num_of_Fixed, 0) + 1 "
            "WHERE question_id = ? AND answer_id = ?",
            (question_id, answer_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def fixed_upsert(question_id, answer_id, user_id):
    """Record a 'Fixed' click on a (question, answer) pair.

    If the link already exists in question_answers, increment its
    num_of_Fixed click counter; otherwise create the link with
    num_of_Fixed = 1. Keeps the question's assigned-answer count in sync.
    """
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE question_answers "
            "SET num_of_Fixed = COALESCE(num_of_Fixed, 0) + 1 "
            "WHERE question_id = ? AND answer_id = ?",
            (question_id, answer_id),
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO question_answers "
                "(question_id, answer_id, user_id, num_of_Fixed) "
                "VALUES (?, ?, ?, 1)",
                (question_id, answer_id, user_id),
            )
            _recount_question_answers(conn, question_id)
        conn.commit()
    finally:
        conn.close()


# Words shorter than this are ignored when matching answers to a question,
# so common filler ("is", "to", "the") doesn't match everything.
_MIN_WORD_LEN = 3


def get_candidate_answers(question_id):
    """Answers relevant to a question, for the side-nav answer section.

    Combines (a) answers already assigned to the question with (b) answers
    whose short_desc/description contains at least one word (>= 3 chars) of
    the question text. Each carries num_of_fixed (the question_answers click
    count, 0 if not linked) and a `fixed` flag (previously resolved 'fixed').
    Ordered by num_of_fixed descending, then short_desc.
    """
    conn = get_db()
    try:
        qrow = conn.execute(
            "SELECT text FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if qrow is None:
            return []

        words = [
            w for w in re.findall(r"[a-z0-9]+", qrow["text"].lower())
            if len(w) >= _MIN_WORD_LEN
        ]
        match_clauses = []
        params = [question_id]
        for w in words:
            match_clauses.append(
                "(LOWER(a.short_desc) LIKE ? "
                "OR LOWER(COALESCE(a.description, '')) LIKE ?)"
            )
            like = f"%{w}%"
            params.extend([like, like])
        # "0" -> no word matches; only already-assigned answers qualify.
        word_filter = " OR ".join(match_clauses) if match_clauses else "0"

        rows = conn.execute(
            f"""
            SELECT a.id, a.short_desc, a.description, a.link,
                   COALESCE(qa.num_of_Fixed, 0) AS num_of_fixed,
                   CASE WHEN qa.answer_id IS NOT NULL THEN 1 ELSE 0 END AS assigned
            FROM answers a
            LEFT JOIN question_answers qa
                   ON qa.answer_id = a.id AND qa.question_id = ?
            WHERE qa.answer_id IS NOT NULL OR ({word_filter})
            ORDER BY num_of_fixed DESC, a.short_desc
            """,
            params,
        ).fetchall()
        answers = [dict(r) for r in rows]
    finally:
        conn.close()

    fixed = get_fixed_answer_ids(question_id)
    for a in answers:
        a["fixed"] = a["id"] in fixed
    return answers
