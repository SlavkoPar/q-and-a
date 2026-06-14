"""Tests for the profile-page data helpers (Step 5).

Adapted from the original spec, which targeted an expenses table that does
not exist in this Q&A app. Here the profile stats come from the user's
groups and question counts instead.
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import DB_PATH, create_user  # noqa: E402
from database.queries import get_summary_stats, get_user_by_id  # noqa: E402

SEED_USER_ID = 1


def _raw():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def temp_user():
    """A freshly created user with no groups; cleaned up afterwards."""
    email = "no_groups_test@example.com"
    conn = _raw()
    conn.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit()
    conn.close()

    user_id = create_user("No Groups", email, "pw12345")
    yield user_id

    conn = _raw()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# --- get_user_by_id ------------------------------------------------- #

def test_get_user_by_id_valid():
    conn = _raw()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (SEED_USER_ID,)
    ).fetchone()
    conn.close()

    user = get_user_by_id(SEED_USER_ID)
    assert user["name"] == row["name"]
    assert user["email"] == row["email"]
    # member_since is the created_at month/year, e.g. "June 2026".
    from datetime import datetime

    expected = datetime.strptime(
        row["created_at"][:19], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")
    assert user["member_since"] == expected


def test_get_user_by_id_missing():
    assert get_user_by_id(999_999) is None


# --- get_summary_stats ---------------------------------------------- #

def test_get_summary_stats_with_groups():
    conn = _raw()
    expected_groups = conn.execute(
        "SELECT COUNT(*) AS n FROM groups WHERE user_id = ?", (SEED_USER_ID,)
    ).fetchone()["n"]
    expected_questions = conn.execute(
        "SELECT COALESCE(SUM(num_of_questions), 0) AS n FROM groups WHERE user_id = ?",
        (SEED_USER_ID,),
    ).fetchone()["n"]
    conn.close()

    stats = get_summary_stats(SEED_USER_ID)
    assert stats["groups"] == expected_groups
    assert stats["questions"] == expected_questions
    assert stats["answers"] == 0


def test_get_summary_stats_no_groups(temp_user):
    assert get_summary_stats(temp_user) == {
        "groups": 0,
        "questions": 0,
        "answers": 0,
    }
