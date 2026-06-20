"""Tests for Fixed / Not-Fixed outcome tracking (Step 15)."""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application  # noqa: E402
from database.db import DB_PATH  # noqa: E402
from database.queries import (  # noqa: E402
    assign_answer,
    fixed_upsert,
    get_candidate_answers,
    get_fixed_answer_ids,
    insert_answer,
    insert_group,
    insert_question,
    record_outcome,
)

SEED_USER_ID = 1
G = "TESTRES_"
A = "TESTRESA_"


def _raw():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup():
    conn = _raw()
    conn.execute(
        "DELETE FROM resolutions WHERE question_id IN "
        "(SELECT id FROM questions WHERE group_id IN "
        "(SELECT id FROM groups WHERE name LIKE ?))", (G + "%",))
    conn.execute(
        "DELETE FROM question_answers WHERE question_id IN "
        "(SELECT id FROM questions WHERE group_id IN "
        "(SELECT id FROM groups WHERE name LIKE ?))", (G + "%",))
    conn.execute(
        "DELETE FROM question_answers WHERE answer_id IN "
        "(SELECT id FROM answers WHERE short_desc LIKE ?)", (A + "%",))
    conn.execute("DELETE FROM answers WHERE short_desc LIKE ?", (A + "%",))
    conn.execute(
        "DELETE FROM questions WHERE group_id IN "
        "(SELECT id FROM groups WHERE name LIKE ?)", (G + "%",))
    conn.execute("DELETE FROM groups WHERE name LIKE ?", (G + "%",))
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def clean():
    _cleanup()
    yield
    _cleanup()


@pytest.fixture
def qa():
    """A question plus a fixed-answer and a not-fixed-answer id."""
    gid = insert_group(SEED_USER_ID, G + "g")
    qid = insert_question(gid, SEED_USER_ID, G + "q")
    a_fixed = insert_answer(SEED_USER_ID, A + "fixed")
    a_other = insert_answer(SEED_USER_ID, A + "other")
    return qid, a_fixed, a_other


@pytest.fixture
def client():
    application.app.testing = True
    return application.app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"email": "demo@my.com", "password": "demo123"})
    return client


# --- unit ----------------------------------------------------------- #

def test_record_and_get_fixed(qa):
    qid, a_fixed, a_other = qa
    record_outcome(qid, a_fixed, SEED_USER_ID, "fixed")
    record_outcome(qid, a_other, SEED_USER_ID, "not_fixed")
    fixed = get_fixed_answer_ids(qid)
    assert a_fixed in fixed
    assert a_other not in fixed


def test_fixed_upsert_creates_then_increments(qa):
    qid, a_fixed, _ = qa

    def num_fixed():
        conn = _raw()
        row = conn.execute(
            "SELECT num_of_Fixed AS n FROM question_answers "
            "WHERE question_id = ? AND answer_id = ?", (qid, a_fixed)
        ).fetchone()
        conn.close()
        return row["n"] if row else None

    assert num_fixed() is None          # not linked yet
    fixed_upsert(qid, a_fixed, SEED_USER_ID)
    assert num_fixed() == 1             # link created at 1
    fixed_upsert(qid, a_fixed, SEED_USER_ID)
    assert num_fixed() == 2             # existing link incremented


def test_candidate_answers_word_match_and_order():
    # Distinctive question word ("kangaroo") that is NOT a substring of the
    # answer prefix, so matching is controlled by the answer text alone.
    gid = insert_group(SEED_USER_ID, G + "wg")
    # Question text has no G/A prefix so word matching is controlled purely by
    # the distinctive words below (cleanup is by group, not question text).
    qid = insert_question(gid, SEED_USER_ID, "kangaroo problem")
    a_match = insert_answer(SEED_USER_ID, A + "kangaroo remedy")
    a_assigned = insert_answer(SEED_USER_ID, A + "zzz unrelated")
    a_nomatch = insert_answer(SEED_USER_ID, A + "zzz nothing")

    # Assigned answers always qualify even without a word match.
    assign_answer(qid, a_assigned, SEED_USER_ID)
    # Give the word-matched answer more Fixed clicks so it ranks first.
    fixed_upsert(qid, a_match, SEED_USER_ID)
    fixed_upsert(qid, a_match, SEED_USER_ID)

    ids = [a["id"] for a in get_candidate_answers(qid)]
    assert a_match in ids               # matched the question word
    assert a_assigned in ids            # assigned, no word match needed
    assert a_nomatch not in ids         # neither matched nor assigned
    assert ids[0] == a_match            # ordered by num_of_fixed desc


# --- route ---------------------------------------------------------- #

def test_outcome_fixed(auth_client, qa):
    qid, a_fixed, _ = qa
    r = auth_client.post(f"/questions/{qid}/answers/{a_fixed}/outcome",
                         data={"outcome": "fixed"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert a_fixed in get_fixed_answer_ids(qid)


def test_outcome_fixed_increments_num_of_fixed(auth_client, qa):
    qid, a_fixed, _ = qa
    assign_answer(qid, a_fixed, SEED_USER_ID)  # link starts at num_of_Fixed = 1

    def num_fixed():
        conn = _raw()
        n = conn.execute(
            "SELECT num_of_Fixed AS n FROM question_answers "
            "WHERE question_id = ? AND answer_id = ?", (qid, a_fixed)
        ).fetchone()["n"]
        conn.close()
        return n

    assert num_fixed() == 1
    auth_client.post(f"/questions/{qid}/answers/{a_fixed}/outcome",
                     data={"outcome": "fixed"})
    assert num_fixed() == 2
    # not_fixed must NOT bump the counter
    auth_client.post(f"/questions/{qid}/answers/{a_fixed}/outcome",
                     data={"outcome": "not_fixed"})
    assert num_fixed() == 2


def test_outcome_invalid(auth_client, qa):
    qid, a_fixed, _ = qa
    r = auth_client.post(f"/questions/{qid}/answers/{a_fixed}/outcome",
                         data={"outcome": "maybe"})
    assert r.status_code == 400
    assert get_fixed_answer_ids(qid) == set()


def test_outcome_requires_login(client, qa):
    qid, a_fixed, _ = qa
    r = client.post(f"/questions/{qid}/answers/{a_fixed}/outcome",
                    data={"outcome": "fixed"})
    assert r.status_code == 401


def test_outcome_other_users_question_404(auth_client):
    r = auth_client.post("/questions/999999/answers/1/outcome",
                         data={"outcome": "fixed"})
    assert r.status_code == 404


def test_outcome_get_not_allowed(auth_client, qa):
    qid, a_fixed, _ = qa
    assert auth_client.get(
        f"/questions/{qid}/answers/{a_fixed}/outcome"
    ).status_code == 405
