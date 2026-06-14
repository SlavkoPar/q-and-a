import json
import os
import sqlite3

from werkzeug.security import generate_password_hash

# Paths -------------------------------------------------------------- #
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
DB_PATH = os.path.join(_PROJECT_ROOT, "my.db")
GROUPS_JSON_PATH = os.path.join(_THIS_DIR, "groups.json")


def get_db():
    """Open a connection to my.db with dict-like rows and FK enforcement."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the users and groups tables. Safe to call repeatedly."""
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_group_id  INTEGER REFERENCES groups(id),
                user_id          INTEGER NOT NULL REFERENCES users(id),
                name             TEXT NOT NULL,
                description      TEXT,
                num_of_questions INTEGER NOT NULL DEFAULT 0,
                created_at       TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert demo data once: a demo user and the groups from groups.json."""
    conn = get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        if existing["n"] > 0:
            return  # Already seeded — avoid duplicates.

        # Demo user becomes id 1, matching user_id in groups.json.
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@my.com", generate_password_hash("demo123")),
        )

        groups = _load_groups()
        # Insert parents before children so FK references resolve.
        for group in _ordered_by_parent(groups):
            conn.execute(
                """
                INSERT INTO groups
                    (id, parent_group_id, user_id, name, description,
                     num_of_questions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group["id"],
                    group.get("group-parent_id"),
                    group["user_id"],
                    group["name"],
                    group.get("description"),
                    group.get("num_of_questions", 0),
                    group["created_at"],
                ),
            )

        conn.commit()
    finally:
        conn.close()


def _load_groups():
    """Read groups from groups.json; return [] if the file is missing."""
    if not os.path.exists(GROUPS_JSON_PATH):
        return []
    with open(GROUPS_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _ordered_by_parent(groups):
    """Sort groups so every parent is inserted before its children."""
    by_id = {g["id"]: g for g in groups}
    ordered = []
    seen = set()

    def visit(group):
        if group["id"] in seen:
            return
        parent_id = group.get("group-parent_id")
        if parent_id is not None and parent_id in by_id:
            visit(by_id[parent_id])
        seen.add(group["id"])
        ordered.append(group)

    for group in groups:
        visit(group)
    return ordered
