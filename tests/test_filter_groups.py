"""Tests for filtering the groups list by name and parent group."""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application  # noqa: E402
from database.db import DB_PATH  # noqa: E402
from database.queries import get_all_groups, insert_group  # noqa: E402

SEED_USER_ID = 1
NAME_PREFIX = "TESTFILT_"


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


def test_filter_by_name():
    insert_group(SEED_USER_ID, NAME_PREFIX + "Alpha")
    insert_group(SEED_USER_ID, NAME_PREFIX + "Beta")
    names = [g["name"] for g in get_all_groups(q=NAME_PREFIX + "Alph")]
    assert names == [NAME_PREFIX + "Alpha"]


def test_filter_by_name_case_insensitive():
    insert_group(SEED_USER_ID, NAME_PREFIX + "Gamma")
    names = [g["name"] for g in get_all_groups(q=NAME_PREFIX.lower() + "gamma")]
    assert NAME_PREFIX + "Gamma" in names


def test_filter_by_parent():
    parent = insert_group(SEED_USER_ID, NAME_PREFIX + "Parent")
    child = insert_group(SEED_USER_ID, NAME_PREFIX + "Child", parent)
    insert_group(SEED_USER_ID, NAME_PREFIX + "Unrelated")
    ids = [g["id"] for g in get_all_groups(parent_id=parent)]
    assert ids == [child]


def test_filter_no_match_empty():
    assert get_all_groups(q=NAME_PREFIX + "zzz-none") == []


def test_no_filter_returns_all():
    insert_group(SEED_USER_ID, NAME_PREFIX + "X")
    assert any(g["name"] == NAME_PREFIX + "X" for g in get_all_groups())


def _row(name):
    # Owned group names render as edit links: >NAME</a> (dropdown options
    # end with </option>, so this targets only the rendered list rows).
    return '>' + name + '</a>'


def test_route_filter_by_name(auth_client):
    insert_group(SEED_USER_ID, NAME_PREFIX + "Findme")
    insert_group(SEED_USER_ID, NAME_PREFIX + "Hideme")
    body = auth_client.get(f"/groups?q={NAME_PREFIX}Findme").get_data(as_text=True)
    assert _row(NAME_PREFIX + "Findme") in body
    assert _row(NAME_PREFIX + "Hideme") not in body


def test_route_filter_by_parent(auth_client):
    parent = insert_group(SEED_USER_ID, NAME_PREFIX + "P")
    insert_group(SEED_USER_ID, NAME_PREFIX + "C", parent)
    body = auth_client.get(f"/groups?parent={parent}").get_data(as_text=True)
    assert _row(NAME_PREFIX + "C") in body
    assert _row(NAME_PREFIX + "P") not in body


def test_route_no_match_shows_message(auth_client):
    body = auth_client.get(f"/groups?q={NAME_PREFIX}nomatch").get_data(as_text=True)
    assert "No groups match this filter." in body


def test_route_unfiltered_ok(auth_client):
    assert auth_client.get("/groups").status_code == 200
