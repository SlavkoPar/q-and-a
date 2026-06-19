import json
import os
import sqlite3

from werkzeug.security import generate_password_hash

# Paths -------------------------------------------------------------- #
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
DB_PATH = os.path.join(_PROJECT_ROOT, "my.db")
IMPORT_DIR = os.path.join(_THIS_DIR, "import")
GROUPS_JSON_PATH = os.path.join(IMPORT_DIR, "groups.json")
QUESTIONS_JSON_PATH = os.path.join(IMPORT_DIR, "questions.json")
ANSWERS_JSON_PATH = os.path.join(IMPORT_DIR, "answers.json")
QUESTION_ANSWERS_JSON_PATH = os.path.join(IMPORT_DIR, "question_answers.json")


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id                INTEGER NOT NULL REFERENCES groups(id),
                user_id                 INTEGER NOT NULL REFERENCES users(id),
                text                    TEXT NOT NULL,
                description             TEXT,
                num_of_assigned_answers INTEGER NOT NULL DEFAULT 0,
                created_at              TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS answers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                short_desc  TEXT NOT NULL,
                description TEXT,
                link        TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS question_answers (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id  INTEGER NOT NULL REFERENCES questions(id),
                answer_id    INTEGER NOT NULL REFERENCES answers(id),
                num_of_Fixed INTEGER DEFAULT 1,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resolutions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES questions(id),
                answer_id   INTEGER NOT NULL REFERENCES answers(id),
                user_id     INTEGER NOT NULL REFERENCES users(id),
                outcome     TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        _ensure_column(conn, "questions", "num_of_assigned_answers",
                       "INTEGER NOT NULL DEFAULT 0")
        # question_answers: 'future' was replaced by 'num_of_Fixed'.
        _ensure_column(conn, "question_answers", "num_of_Fixed",
                       "INTEGER DEFAULT 1")
        _drop_column(conn, "question_answers", "future")
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn, table, column, decl):
    """Add `column` to `table` if an older DB predates it (idempotent migration)."""
    cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _drop_column(conn, table, column):
    """Drop `column` from `table` if present (SQLite >= 3.35)."""
    cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column in cols:
        conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


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

        groups = _load_json(GROUPS_JSON_PATH)
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

        # Questions reference groups, so they are seeded after the groups.
        for question in _load_json(QUESTIONS_JSON_PATH):
            conn.execute(
                """
                INSERT INTO questions
                    (id, group_id, user_id, text, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    question["id"],
                    question["group_id"],
                    question["user_id"],
                    question["text"],
                    question.get("description"),
                    question["created_at"],
                ),
            )

        for answer in _load_json(ANSWERS_JSON_PATH):
            conn.execute(
                """
                INSERT INTO answers
                    (id, user_id, short_desc, description, link, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    answer["id"],
                    answer["user_id"],
                    answer["short_desc"],
                    answer.get("description"),
                    answer.get("link"),
                    answer["created_at"],
                ),
            )

        for link in _load_json(QUESTION_ANSWERS_JSON_PATH):
            conn.execute(
                """
                INSERT INTO question_answers
                    (id, question_id, answer_id, num_of_Fixed, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    link["id"],
                    link["question_id"],
                    link["answer_id"],
                    link.get("num_of_Fixed", 1),
                    link["user_id"],
                    link["created_at"],
                ),
            )

        # Keep derived counts consistent with the seeded rows.
        conn.execute(
            "UPDATE groups SET num_of_questions = "
            "(SELECT COUNT(*) FROM questions WHERE questions.group_id = groups.id)"
        )
        conn.execute(
            "UPDATE questions SET num_of_assigned_answers = "
            "(SELECT COUNT(*) FROM question_answers "
            " WHERE question_answers.question_id = questions.id)"
        )

        conn.commit()
    finally:
        conn.close()


def create_user(name, email, password):
    """Hash the password and insert a new user; return the new user's id.

    Raises sqlite3.IntegrityError if the email is already registered
    (the users.email UNIQUE constraint).
    """
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_by_email(email):
    """Return the user row matching email, or None if no such user exists."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def _load_json(path):
    """Read a JSON array from path; return [] if the file is missing."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
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
