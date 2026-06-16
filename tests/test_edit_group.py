"""Tests for Edit Group + the groups list page (Q&A schema).

The groups list shows ALL groups regardless of owner; editing is owner-scoped.
"""

import os
import sqlite3
import sys

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application  # noqa: E402
from database.db import DB_PATH  # noqa: E402
from database.queries import (  # noqa: E402
    get_all_groups,
    get_group_by_id,
    insert_group,
    update_group,
)

SEED_USER_ID = 1
NAME_PREFIX = "TESTEDIT_"
OTHER_EMAIL = "other_owner_test@example.com"


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
        ("Other Owner", OTHER_EMAIL, generate_password_hash("pw123456")),
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


def test_get_group_by_id_owner():
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g", None, "d")
    assert get_group_by_id(gid, SEED_USER_ID)["name"] == NAME_PREFIX + "g"


def test_get_group_by_id_wrong_user():
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g", None, "d")
    assert get_group_by_id(gid, 999_999) is None


def test_get_group_by_id_missing():
    assert get_group_by_id(999_999, SEED_USER_ID) is None


def test_update_group_owner():
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "old", None, "d")
    assert update_group(gid, SEED_USER_ID, NAME_PREFIX + "new", None, "d2") == 1
    assert get_group_by_id(gid, SEED_USER_ID)["name"] == NAME_PREFIX + "new"


def test_update_group_wrong_user():
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "keep", None, "d")
    assert update_group(gid, 999_999, NAME_PREFIX + "hacked", None, None) == 0
    assert get_group_by_id(gid, SEED_USER_ID)["name"] == NAME_PREFIX + "keep"


def test_list_shows_all_groups(auth_client, other_user_group):
    _other_id, group_id = other_user_group
    body = auth_client.get("/groups").get_data(as_text=True)
    assert NAME_PREFIX + "foreign" in body
    assert "Other Owner" in body
    assert any(g["id"] == group_id for g in get_all_groups())


def test_edit_get_requires_login(client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "g", None, None)
    r = client.get(f"/groups/{gid}/edit")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_edit_get_own_group_prefilled(auth_client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "mine", None, "hello")
    body = auth_client.get(f"/groups/{gid}/edit").get_data(as_text=True)
    assert NAME_PREFIX + "mine" in body and "hello" in body


def test_edit_other_users_group_404(auth_client, other_user_group):
    _other_id, group_id = other_user_group
    assert auth_client.get(f"/groups/{group_id}/edit").status_code == 404


def test_edit_missing_404(auth_client):
    assert auth_client.get("/groups/999999/edit").status_code == 404


def test_edit_post_valid_redirects_and_updates(auth_client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "before", None, "d")
    r = auth_client.post(
        f"/groups/{gid}/edit",
        data={"name": NAME_PREFIX + "after", "description": "new",
              "parent_group_id": ""},
    )
    assert r.status_code == 302 and "/groups" in r.headers["Location"]
    assert get_group_by_id(gid, SEED_USER_ID)["name"] == NAME_PREFIX + "after"


def test_edit_post_blank_name_rerenders(auth_client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "x", None, None)
    r = auth_client.post(f"/groups/{gid}/edit", data={"name": "  "})
    assert r.status_code == 200 and "required" in r.get_data(as_text=True)


def test_edit_post_self_parent_rejected(auth_client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "self", None, None)
    r = auth_client.post(
        f"/groups/{gid}/edit",
        data={"name": NAME_PREFIX + "self", "parent_group_id": str(gid)},
    )
    assert r.status_code == 200 and "its own parent" in r.get_data(as_text=True)


def test_edit_post_blank_description_null(auth_client):
    gid = insert_group(SEED_USER_ID, NAME_PREFIX + "d", None, "had desc")
    r = auth_client.post(
        f"/groups/{gid}/edit",
        data={"name": NAME_PREFIX + "d", "description": "  "},
    )
    assert r.status_code == 302
    assert get_group_by_id(gid, SEED_USER_ID)["description"] is None
