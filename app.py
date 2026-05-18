import os
import sqlite3
import uuid
import traceback
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import (
    apology,
    allowed_audio_file,
    format_timestamp,
    login_required,
    parse_dialogue_script,
    sanitize_avatar,
    validate_language,
    SUPPORTED_LANGUAGES,
)

# =========================================================
# APP SETUP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "change_this_secret_before_production"
)

app.config["DATABASE"] = "instance/history.db"
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs("instance", exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =========================================================
# DATABASE
# =========================================================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    posts = query_db("""
        SELECT posts.*, users.username, users.avatar,
        (SELECT COUNT(*) FROM bookmarks WHERE bookmarks.post_id = posts.id) AS bookmark_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    """)

    formatted = []

    for p in posts:
        formatted.append({
            "id": p["id"],
            "title": p["title"],
            "username": p["username"],
            "avatar": sanitize_avatar(p["avatar"] or ""),
            "type": p["type"],
            "language": p["language"],
            "likes": p["likes"] or 0,
            "views": p["views"] or 0,
            "bookmark_count": p["bookmark_count"] or 0,
            "preview": (p["content"] or "")[:150],
            "created_at": format_timestamp(p["created_at"]),
        })

    return render_template("index.html", posts=formatted)

# =========================================================
# FIXED POST ROUTE (THIS WAS YOUR CRASH)
# =========================================================

@app.route("/post/<int:post_id>")
def post(post_id):

    try:
        post = query_db("""
            SELECT posts.*, users.username, users.avatar
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.id = ?
        """, (post_id,), one=True)

        if not post:
            return render_template(
                "apology.html",
                title="Not Found",
                message="Post not found"
            ), 404

        execute_db("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))

        post = dict(post)
        post["avatar"] = sanitize_avatar(post["avatar"] or "👤")
        post["likes"] = post["likes"] or 0
        post["views"] = post["views"] or 0
        post["speed"] = float(post.get("speed") or 1)

        parsed = []
        if post["type"] == "dialogue":
            parsed = parse_dialogue_script(post["content"])

        related = query_db("""
            SELECT id, title, type
            FROM posts
            WHERE language = ?
            AND id != ?
            ORDER BY RANDOM()
            LIMIT 4
        """, (post["language"], post_id))

        return render_template(
            "post.html",
            post=post,
            parsed_dialogue=parsed,
            related_posts=related
        )

    except Exception:
        print(traceback.format_exc())
        return render_template(
            "apology.html",
            title="Error",
            message="Internal error loading post"
        ), 500

# =========================================================
# RENDER SAFE START (IMPORTANT FIX)
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
