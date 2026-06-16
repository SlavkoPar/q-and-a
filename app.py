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
from database.queries import (
    count_child_groups,
    delete_group,
    delete_question,
    get_all_groups,
    get_group_by_id,
    get_question_by_id,
    get_questions_for_group,
    get_summary_stats,
    get_user_by_id,
    get_user_groups,
    insert_group,
    insert_question,
    update_group,
    update_question,
)


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


def _build_group_tree(groups):
    """Nest a flat group list by parent_group_id, sorted by name at each level."""
    by_id = {g["id"]: {**g, "children": []} for g in groups}
    roots = []
    for node in by_id.values():
        parent = by_id.get(node["parent_group_id"])
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)

    def sort_nodes(nodes):
        nodes.sort(key=lambda n: n["name"].lower())
        for n in nodes:
            sort_nodes(n["children"])

    sort_nodes(roots)
    return roots


@app.route("/groups")
def groups():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Optional filters: by name (q) and/or by parent group (parent).
    q = request.args.get("q", "").strip()
    parent_raw = request.args.get("parent", "").strip()
    parent_id = int(parent_raw) if parent_raw.isdigit() else None
    filter_active = bool(q) or parent_id is not None
    parent_options = get_all_groups()

    if filter_active:
        matches = get_all_groups(q=q or None, parent_id=parent_id)
        return render_template(
            "groups/list.html", flat=matches, filter_active=True,
            q=q, parent_id=parent_raw, parent_options=parent_options,
        )

    tree = _build_group_tree(parent_options)
    return render_template(
        "groups/list.html", tree=tree, filter_active=False,
        q="", parent_id="", parent_options=parent_options,
    )


@app.route("/groups/add", methods=["GET", "POST"])
def add_group():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    parent_groups = get_user_groups(user_id)

    if request.method == "GET":
        parent_arg = request.args.get("parent", "").strip()
        valid_ids = {str(g["id"]) for g in parent_groups}
        preselect = parent_arg if parent_arg in valid_ids else ""
        form = {"name": "", "description": "", "parent_group_id": preselect}
        return render_template(
            "groups/add_group.html", parent_groups=parent_groups, form=form
        )
    if request.method != "POST":
        abort(405)

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    parent_raw = request.form.get("parent_group_id", "").strip()
    form = {"name": name, "description": description, "parent_group_id": parent_raw}

    def reject(message):
        flash(message)
        return render_template(
            "groups/add_group.html", parent_groups=parent_groups, form=form
        )

    if not name:
        return reject("Group name is required.")

    parent_group_id = None
    if parent_raw:
        valid_ids = {str(g["id"]) for g in parent_groups}
        if parent_raw not in valid_ids:
            return reject("Please choose a valid parent group.")
        parent_group_id = int(parent_raw)

    insert_group(user_id, name, parent_group_id, description or None)
    return redirect(url_for("groups"))


@app.route("/groups/<int:id>/edit", methods=["GET", "POST"])
def edit_group(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    group = get_group_by_id(id, user_id)
    if group is None:
        abort(404)

    parent_groups = [g for g in get_user_groups(user_id) if g["id"] != id]
    questions = get_questions_for_group(id)

    if request.method == "GET":
        form = {
            "name": group["name"],
            "description": group["description"] or "",
            "parent_group_id": str(group["parent_group_id"] or ""),
        }
        return render_template(
            "groups/edit_group.html", group=group,
            parent_groups=parent_groups, questions=questions, form=form,
        )
    if request.method != "POST":
        abort(405)

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    parent_raw = request.form.get("parent_group_id", "").strip()
    form = {"name": name, "description": description, "parent_group_id": parent_raw}

    def reject(message):
        flash(message)
        return render_template(
            "groups/edit_group.html", group=group,
            parent_groups=parent_groups, questions=questions, form=form,
        )

    if not name:
        return reject("Group name is required.")

    parent_group_id = None
    if parent_raw:
        if parent_raw == str(id):
            return reject("A group cannot be its own parent.")
        valid_ids = {str(g["id"]) for g in parent_groups}
        if parent_raw not in valid_ids:
            return reject("Please choose a valid parent group.")
        parent_group_id = int(parent_raw)

    update_group(id, user_id, name, parent_group_id, description or None)
    return redirect(url_for("groups"))


@app.route("/groups/<int:id>/delete", methods=["POST"])
def delete_group_route(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if get_group_by_id(id, user_id) is None:
        abort(404)

    if count_child_groups(id, user_id) > 0:
        flash("Remove or re-parent this group's child groups before deleting it.")
        return redirect(url_for("groups"))

    delete_group(id, user_id)
    return redirect(url_for("groups"))


# ------------------------------------------------------------------ #
# Questions (maintained from the group edit page)                     #
# ------------------------------------------------------------------ #

@app.route("/groups/<int:id>/questions/add", methods=["POST"])
def add_question(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))
    if get_group_by_id(id, user_id) is None:
        abort(404)

    text = request.form.get("text", "").strip()
    description = request.form.get("description", "").strip()
    if not text:
        flash("Question text is required.")
        return redirect(url_for("edit_group", id=id) + "#questions")

    insert_question(id, user_id, text, description or None)
    return redirect(url_for("edit_group", id=id) + "#questions")


@app.route("/questions/<int:qid>/edit", methods=["POST"])
def edit_question(qid):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    question = get_question_by_id(qid, user_id)
    if question is None:
        abort(404)

    text = request.form.get("text", "").strip()
    description = request.form.get("description", "").strip()
    group_id = question["group_id"]
    if not text:
        flash("Question text is required.")
        return redirect(url_for("edit_group", id=group_id) + "#questions")

    update_question(qid, user_id, text, description or None)
    return redirect(url_for("edit_group", id=group_id) + "#questions")


@app.route("/questions/<int:qid>/delete", methods=["POST"])
def delete_question_route(qid):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    question = get_question_by_id(qid, user_id)
    if question is None:
        abort(404)

    group_id = question["group_id"]
    delete_question(qid, user_id)
    return redirect(url_for("edit_group", id=group_id) + "#questions")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
