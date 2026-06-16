"""Tests for the Add Group feature (Q&A schema)."""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application  # noqa: E402
from database.db import DB_PATH  # noqa: E402
from database.queries import insert_group  # noqa: E402

SEED_USER_ID = 1
NAME_PREFIX = "TESTGRP_"


def _raw():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup():
    conn = _raw()
    conn.execute("DELETE FROM groups WHERE name LIKE ?", (NAME_PREFIX + "%",))
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def clean_groups():
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


def test_insert_group_inserts_row():
    new_id = insert_group(SEED_USER_ID, NAME_PREFIX + "unit", None, "desc")
    conn = _raw()
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    assert row is not None
    assert row["name"] == NAME_PREFIX + "unit"
    assert row["description"] == "desc"
    assert row["parent_group_id"] is None
    assert row["num_of_questions"] == 0


def test_get_requires_login(client):
    r = client.get("/groups/add")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_post_requires_login(client):
    r = client.post("/groups/add", data={"name": NAME_PREFIX + "x"})
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_get_renders_form(auth_client):
    r = auth_client.get("/groups/add")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "<form" in body and 'method="POST"' in body


def test_post_valid_redirects_and_inserts(auth_client):
    r = auth_client.post(
        "/groups/add",
        data={"name": NAME_PREFIX + "valid", "description": "desc",
              "parent_group_id": ""},
    )
    assert r.status_code == 302 and "/groups" in r.headers["Location"]
    conn = _raw()
    row = conn.execute(
        "SELECT * FROM groups WHERE name = ?", (NAME_PREFIX + "valid",)
    ).fetchone()
    conn.close()
    assert row is not None and row["description"] == "desc"


def test_post_missing_name_rerenders(auth_client):
    r = auth_client.post("/groups/add", data={"name": "  ", "description": "x"})
    assert r.status_code == 200 and "required" in r.get_data(as_text=True)


def test_post_invalid_parent_rerenders(auth_client):
    r = auth_client.post(
        "/groups/add",
        data={"name": NAME_PREFIX + "bad", "parent_group_id": "999999"},
    )
    assert r.status_code == 200
    assert "valid parent group" in r.get_data(as_text=True)
    conn = _raw()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM groups WHERE name = ?", (NAME_PREFIX + "bad",)
    ).fetchone()["n"]
    conn.close()
    assert n == 0


def test_post_no_description_stores_null(auth_client):
    r = auth_client.post(
        "/groups/add",
        data={"name": NAME_PREFIX + "nodesc", "description": "  "},
    )
    assert r.status_code == 302
    conn = _raw()
    row = conn.execute(
        "SELECT * FROM groups WHERE name = ?", (NAME_PREFIX + "nodesc",)
    ).fetchone()
    conn.close()
    assert row is not None and row["description"] is None
