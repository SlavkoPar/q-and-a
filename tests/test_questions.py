"""Tests for the group-scoped Questions feature (Q&A schema)."""

import os
import sqlite3
import sys

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application  # noqa: E402
from database.db import DB_PATH  # noqa: E402
from database.queries import (  # noqa: E402
    delete_question,
    get_question_by_id,
    get_questions_for_group,
    insert_group,
    insert_question,
    update_question,
)

SEED_USER_ID = 1
NAME_PREFIX = "TESTQ_"
OTHER_EMAIL = "q_other_test@example.com"


def _raw():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup():
    conn = _raw()
    conn.execute(
        "DELETE FROM questions WHERE group_id IN "
        "(SELECT id FROM groups WHERE name LIKE ?)", (NAME_PREFIX + "%",))
    conn.execute("DELETE FROM groups WHERE name LIKE ?", (NAME_PREFIX + "%",))
    conn.execute("DELETE FROM users WHERE email = ?", (OTHER_EMAIL,))
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def clean():
    _cleanup()
    yield
    _cleanup()


@pytest.fixture
def group_id():
    return insert_group(SEED_USER_ID, NAME_PREFIX + "g")


@pytest.fixture
def client():
    application.app.testing = True
    return application.app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"email": "demo@my.com", "password": "demo123"})
    return client


def _num_questions(gid):
    conn = _raw()
    n = conn.execute(
        "SELECT num_of_questions AS n FROM groups WHERE id = ?", (gid,)
    ).fetchone()["n"]
    conn.close()
    return n


def test_insert_question_syncs_count(group_id):
    qid = insert_question(group_id, SEED_USER_ID, "What?", "desc")
    q = get_question_by_id(qid, SEED_USER_ID)
    assert q["text"] == "What?" and q["description"] == "desc"
    assert _num_questions(group_id) == 1


def test_get_questions_for_group(group_id):
    insert_question(group_id, SEED_USER_ID, "Q1")
    insert_question(group_id, SEED_USER_ID, "Q2")
    assert [q["text"] for q in get_questions_for_group(group_id)] == ["Q1", "Q2"]


def test_get_question_by_id_wrong_user(group_id):
    qid = insert_question(group_id, SEED_USER_ID, "Q")
    assert get_question_by_id(qid, 999_999) is None


def test_update_question_owner(group_id):
    qid = insert_question(group_id, SEED_USER_ID, "old", None)
    assert update_question(qid, SEED_USER_ID, "new", "d") == 1
    assert get_question_by_id(qid, SEED_USER_ID)["text"] == "new"


def test_update_question_wrong_user(group_id):
    qid = insert_question(group_id, SEED_USER_ID, "keep")
    assert update_question(qid, 999_999, "hacked", None) == 0
    assert get_question_by_id(qid, SEED_USER_ID)["text"] == "keep"


def test_delete_question_syncs_count(group_id):
    qid = insert_question(group_id, SEED_USER_ID, "Q")
    assert _num_questions(group_id) == 1
    assert delete_question(qid, SEED_USER_ID) == 1
    assert _num_questions(group_id) == 0


def test_delete_question_wrong_user(group_id):
    qid = insert_question(group_id, SEED_USER_ID, "Q")
    assert delete_question(qid, 999_999) == 0
    assert get_question_by_id(qid, SEED_USER_ID) is not None


def test_add_question_requires_login(client, group_id):
    r = client.post(f"/groups/{group_id}/questions/add", data={"text": "Q"})
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_add_question_valid(auth_client, group_id):
    r = auth_client.post(
        f"/groups/{group_id}/questions/add",
        data={"text": "How do I X?", "description": "ctx"},
    )
    assert r.status_code == 302
    assert f"/groups/{group_id}/edit" in r.headers["Location"]
    assert get_questions_for_group(group_id)[0]["text"] == "How do I X?"


def test_add_question_blank_text(auth_client, group_id):
    r = auth_client.post(f"/groups/{group_id}/questions/add", data={"text": "  "})
    assert r.status_code == 302
    assert get_questions_for_group(group_id) == []


def test_add_question_foreign_group_404(auth_client):
    conn = _raw()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Q Other", OTHER_EMAIL, generate_password_hash("pw123456")),
    )
    other_id = cur.lastrowid
    gcur = conn.execute(
        "INSERT INTO groups (user_id, name) VALUES (?, ?)",
        (other_id, NAME_PREFIX + "foreign"),
    )
    foreign_gid = gcur.lastrowid
    conn.commit()
    conn.close()
    r = auth_client.post(f"/groups/{foreign_gid}/questions/add", data={"text": "Q"})
    assert r.status_code == 404


def test_edit_question_route(auth_client, group_id):
    qid = insert_question(group_id, SEED_USER_ID, "old")
    r = auth_client.post(f"/questions/{qid}/edit",
                         data={"text": "new", "description": ""})
    assert r.status_code == 302
    assert get_question_by_id(qid, SEED_USER_ID)["text"] == "new"
    assert get_question_by_id(qid, SEED_USER_ID)["description"] is None


def test_edit_question_missing_404(auth_client):
    assert auth_client.post("/questions/999999/edit",
                            data={"text": "x"}).status_code == 404


def test_delete_question_route(auth_client, group_id):
    qid = insert_question(group_id, SEED_USER_ID, "Q")
    r = auth_client.post(f"/questions/{qid}/delete")
    assert r.status_code == 302
    assert get_question_by_id(qid, SEED_USER_ID) is None


def test_question_routes_are_post_only(auth_client, group_id):
    qid = insert_question(group_id, SEED_USER_ID, "Q")
    assert auth_client.get(f"/groups/{group_id}/questions/add").status_code == 405
    assert auth_client.get(f"/questions/{qid}/edit").status_code == 405
    assert auth_client.get(f"/questions/{qid}/delete").status_code == 405


def test_edit_page_shows_questions_section(auth_client, group_id):
    insert_question(group_id, SEED_USER_ID, "Visible question")
    body = auth_client.get(f"/groups/{group_id}/edit").get_data(as_text=True)
    assert "Questions" in body and "Visible question" in body and "Add Question" in body
