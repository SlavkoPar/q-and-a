"""Tests for Delete Group (Q&A schema): owner-scoped, refuses non-empty parents."""

import os
import sqlite3
import sys

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application  # noqa: E402
from database.db import DB_PATH  # noqa: E402
from database.queries import count_child_groups, delete_group, insert_group  # noqa: E402

SEED_USER_ID = 1
NAME_PREFIX = "TESTDEL_"
OTHER_EMAIL = "del_other_test@example.com"


def _raw():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup():
    conn = _raw()
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
def client():
    application.app.testing = True
    return application.app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"email": "demo@my.com", "password": "demo123"})
    return client


@pytest.fixture
def other_user_group():
    conn = _raw()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Del Other", OTHER_EMAIL, generate_password_hash("pw123456")),
    )
    other_id = cur.lastrowid
    gcur = conn.execute(
        "INSERT INTO groups (user_id, name) VALUES (?, ?)",
        (other_id, NAME_PREFIX + "foreign"),
    )
    group_id = gcur.lastrowid
    conn.commit()
    conn.close()
    return other_id, group_id


def _exists(group_id):
    conn = _raw()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM groups WHERE id = ?", (group_id,)
    ).fetchone()["n"]
    conn.close()
    return n == 1


def test_delete_group_owner():
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g")
    assert delete_group(gid, SEED_USER_ID) == 1
    assert not _exists(gid)


def test_delete_group_wrong_user():
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g")
    assert delete_group(gid, 999_999) == 0
    assert _exists(gid)


def test_delete_group_missing():
    assert delete_group(999_999, SEED_USER_ID) == 0


def test_count_child_groups():
    parent = insert_group(SEED_USER_ID, NAME_PREFIX + "parent")
    insert_group(SEED_USER_ID, NAME_PREFIX + "c1", parent)
    insert_group(SEED_USER_ID, NAME_PREFIX + "c2", parent)
    assert count_child_groups(parent, SEED_USER_ID) == 2


def test_delete_requires_login(client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g")
    r = client.post(f"/groups/{gid}/delete")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_delete_own_childless(auth_client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g")
    r = auth_client.post(f"/groups/{gid}/delete")
    assert r.status_code == 302 and "/groups" in r.headers["Location"]
    assert not _exists(gid)


def test_delete_own_with_children_refused(auth_client):
    parent = insert_group(SEED_USER_ID, NAME_PREFIX + "parent")
    insert_group(SEED_USER_ID, NAME_PREFIX + "child", parent)
    r = auth_client.post(f"/groups/{parent}/delete")
    assert r.status_code == 302 and "/groups" in r.headers["Location"]
    assert _exists(parent)


def test_delete_other_users_group_404(auth_client, other_user_group):
    _other_id, group_id = other_user_group
    assert auth_client.post(f"/groups/{group_id}/delete").status_code == 404
    assert _exists(group_id)


def test_delete_missing_404(auth_client):
    assert auth_client.post("/groups/999999/delete").status_code == 404


def test_delete_get_not_allowed(auth_client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g")
    assert auth_client.get(f"/groups/{gid}/delete").status_code == 405
