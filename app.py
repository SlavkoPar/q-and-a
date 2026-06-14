import os
import sqlite3

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
)
from database.queries import get_summary_stats, get_user_by_id


def _initials(name):
    """First letters of the first two words of a name, uppercased."""
    parts = name.split()
    return "".join(part[0] for part in parts[:2]).upper()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Ensure the database schema and demo data are ready before serving.
with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    if request.method != "POST":
        abort(405)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm_password:
        flash("All fields are required.")
        return render_template("register.html")

    if password != confirm_password:
        flash("Passwords do not match.")
        return render_template("register.html")

    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        flash("Email already registered.")
        return render_template("register.html")

    flash("Account created — please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    if request.method != "POST":
        abort(405)

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.")
        return render_template("login.html")

    session["user_id"] = user["id"]
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    # Authentication guard — only logged-in users may view their profile.
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    # Step 5: real data. Pull the user and their stats from the database.
    user = get_user_by_id(user_id)
    if user is None:
        # Session points at a user that no longer exists — force re-login.
        session.clear()
        return redirect(url_for("login"))

    user = {**user, "initials": _initials(user["name"])}

    summary = get_summary_stats(user_id)
    stats = [
        {"label": "Groups", "value": summary["groups"]},
        {"label": "Questions", "value": summary["questions"]},
        {"label": "Answers", "value": summary["answers"]},
    ]
    return render_template("profile.html", user=user, stats=stats)


@app.route("/groups")
def groups():
    return "Groups page — coming soon"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
