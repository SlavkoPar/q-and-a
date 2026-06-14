"""Pure data-access helpers for the profile page.

No Flask imports here — each function opens a connection via get_db(),
runs a parameterised query, and closes the connection before returning.

Note: this app is the Q&A tool (users + groups). There is no expenses
table, so the profile's summary stats are derived from the user's groups
and question counts rather than spending.
"""

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
    finally:
        conn.close()

    return {
        "groups": row["groups"],
        "questions": row["questions"],
        "answers": 0,
    }
