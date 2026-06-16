"""Tests for the Answers feature: answer CRUD + question assignment."""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application  # noqa: E402
from database.db import DB_PATH  # noqa: E402
from database.queries import (  # noqa: E402
    assign_answer,
    delete_answer,
    get_all_answers,
    get_answer_by_id,
    get_assigned_answers,
    get_unassigned_answers,
    insert_answer,
    insert_group,
    insert_question,
    unassign_answer,
    update_answer,
)

SEED_USER_ID = 1
A = "TESTANS_"
G = "TESTANSG_"


def _raw():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup():
    conn = _raw()
    conn.execute(
        "DELETE FROM question_answers WHERE answer_id IN "
        "(SELECT id FROM answers WHERE short_desc LIKE ?)", (A + "%",))
    conn.execute(
        "DELETE FROM question_answers WHERE question_id IN "
        "(SELECT id FROM questions WHERE group_id IN "
        "(SELECT id FROM groups WHERE name LIKE ?))", (G + "%",))
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
def client():
    application.app.testing = True
    return application.app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"email": "demo@my.com", "password": "demo123"})
    return client


@pytest.fixture
def question_id():
    gid = insert_group(SEED_USER_ID, G + "g")
    return insert_question(gid, SEED_USER_ID, G + "q")


def _assigned_count(qid):
    conn = _raw()
    n = conn.execute(
        "SELECT num_of_assigned_answers AS n FROM questions WHERE id = ?", (qid,)
    ).fetchone()["n"]
    conn.close()
    return n


def test_insert_and_get_answer():
    aid = insert_answer(SEED_USER_ID, A + "one", "desc", "http://x")
    a = get_answer_by_id(aid, SEED_USER_ID)
    assert a["short_desc"] == A + "one" and a["link"] == "http://x"


def test_get_all_answers_filter():
    insert_answer(SEED_USER_ID, A + "Banana")
    insert_answer(SEED_USER_ID, A + "Cherry")
    assert [a["short_desc"] for a in get_all_answers(q=A + "banana")] == [A + "Banana"]


def test_get_answer_wrong_user():
    aid = insert_answer(SEED_USER_ID, A + "x")
    assert get_answer_by_id(aid, 999_999) is None


def test_update_answer_owner():
    aid = insert_answer(SEED_USER_ID, A + "old")
    assert update_answer(aid, SEED_USER_ID, A + "new", None, None) == 1
    assert get_answer_by_id(aid, SEED_USER_ID)["short_desc"] == A + "new"


def test_update_answer_wrong_user():
    aid = insert_answer(SEED_USER_ID, A + "keep")
    assert update_answer(aid, 999_999, A + "hack", None, None) == 0


def test_delete_answer_cascades_links(question_id):
    aid = insert_answer(SEED_USER_ID, A + "del")
    assign_answer(question_id, aid, SEED_USER_ID)
    assert _assigned_count(question_id) == 1
    assert delete_answer(aid, SEED_USER_ID) == 1
    assert get_assigned_answers(question_id) == []
    assert _assigned_count(question_id) == 0


def test_assign_and_unassign(question_id):
    aid = insert_answer(SEED_USER_ID, A + "asg")
    assert assign_answer(question_id, aid, SEED_USER_ID) is True
    assert assign_answer(question_id, aid, SEED_USER_ID) is False  # no duplicate
    assert [a["id"] for a in get_assigned_answers(question_id)] == [aid]
    assert _assigned_count(question_id) == 1
    assert unassign_answer(question_id, aid) == 1
    assert _assigned_count(question_id) == 0


def test_unassigned_excludes_assigned(question_id):
    aid = insert_answer(SEED_USER_ID, A + "u")
    assign_answer(question_id, aid, SEED_USER_ID)
    assert aid not in [a["id"] for a in get_unassigned_answers(question_id)]


def test_answers_requires_login(client):
    r = client.get("/answers")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_answers_list_and_filter(auth_client):
    insert_answer(SEED_USER_ID, A + "Findable")
    body = auth_client.get(f"/answers?q={A}Findable").get_data(as_text=True)
    assert A + "Findable" in body


def test_add_answer_valid(auth_client):
    r = auth_client.post("/answers/add",
                         data={"short_desc": A + "added", "description": "", "link": ""})
    assert r.status_code == 302 and "/answers" in r.headers["Location"]
    assert any(a["short_desc"] == A + "added" for a in get_all_answers())


def test_add_answer_blank(auth_client):
    r = auth_client.post("/answers/add", data={"short_desc": "  "})
    assert r.status_code == 200 and "required" in r.get_data(as_text=True)


def test_edit_answer_owner(auth_client):
    aid = insert_answer(SEED_USER_ID, A + "e")
    r = auth_client.post(f"/answers/{aid}/edit",
                         data={"short_desc": A + "edited", "description": "", "link": ""})
    assert r.status_code == 302
    assert get_answer_by_id(aid, SEED_USER_ID)["short_desc"] == A + "edited"


def test_edit_answer_missing_404(auth_client):
    assert auth_client.post("/answers/999999/edit",
                            data={"short_desc": "x"}).status_code == 404


def test_delete_answer_route(auth_client):
    aid = insert_answer(SEED_USER_ID, A + "d")
    r = auth_client.post(f"/answers/{aid}/delete")
    assert r.status_code == 302
    assert get_answer_by_id(aid, SEED_USER_ID) is None


def test_assign_route(auth_client, question_id):
    aid = insert_answer(SEED_USER_ID, A + "r")
    r = auth_client.post(f"/questions/{question_id}/answers/assign",
                         data={"answer_id": aid})
    assert r.status_code == 302
    assert aid in [a["id"] for a in get_assigned_answers(question_id)]


def test_unassign_route(auth_client, question_id):
    aid = insert_answer(SEED_USER_ID, A + "r2")
    assign_answer(question_id, aid, SEED_USER_ID)
    r = auth_client.post(f"/questions/{question_id}/answers/{aid}/unassign")
    assert r.status_code == 302
    assert get_assigned_answers(question_id) == []


def test_assign_foreign_question_404(auth_client):
    assert auth_client.post("/questions/999999/answers/assign",
                            data={"answer_id": 1}).status_code == 404
