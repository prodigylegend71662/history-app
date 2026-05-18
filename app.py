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

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

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

# FREE RENDER SAFE
app.config["DATABASE"] = "instance/history.db"

app.config["UPLOAD_FOLDER"] = "static/uploads"

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs("instance", exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =========================================================
# ADMIN
# =========================================================

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "developer"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "historygod123"
)

# =========================================================
# DATABASE HELPERS
# =========================================================

def get_db():

    if "db" not in g:

        g.db = sqlite3.connect(
            app.config["DATABASE"],
            check_same_thread=False
        )

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
# ADMIN DECORATOR
# =========================================================

def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("is_admin"):
            return apology("Admin only", 403)

        return f(*args, **kwargs)

    return decorated_function

# =========================================================
# CONTEXT
# =========================================================

@app.context_processor
def inject_globals():

    return {
        "current_year": datetime.now().year,

        "logged_in":
            session.get("user_id") is not None,

        "current_user": {
            "id": session.get("user_id"),
            "username": session.get("username"),
        }
    }

# =========================================================
# HOME FEED
# =========================================================

@app.route("/")
def index():

    language_filter = request.args.get("lang")
    type_filter = request.args.get("type")
    search_query = request.args.get("search")

    sql = """
        SELECT
            posts.*,
            users.username,
            users.avatar,

            (
                SELECT COUNT(*)
                FROM bookmarks
                WHERE bookmarks.post_id = posts.id
            ) AS bookmark_count

        FROM posts

        JOIN users
        ON posts.user_id = users.id

        WHERE 1=1
    """

    params = []

    if language_filter:
        sql += " AND posts.language = ? "
        params.append(language_filter)

    if type_filter:
        sql += " AND posts.type = ? "
        params.append(type_filter)

    if search_query:
        sql += " AND posts.title LIKE ? "
        params.append(f"%{search_query}%")

    sql += """
        ORDER BY
            (posts.likes * 3 + posts.views * 0.25) DESC,
            posts.created_at DESC
    """

    posts = query_db(sql, params)

    formatted_posts = []

    for p in posts:
        preview = ""

        if p["type"] == "dialogue":

            parsed = parse_dialogue_script(p["content"])

            if parsed:
                preview = parsed[0]["text"][:180]

        elif p["type"] == "read-only":

            preview = (p["content"] or "")[:180]

        elif p["type"] == "audio":

            preview = "Audio narration ready to play."

        formatted_posts.append({

            "id": p["id"],
            "title": p["title"],
            "username": p["username"],
            "avatar": sanitize_avatar(p["avatar"] if p["avatar"] else ""),
            "type": p["type"],
            "language": p["language"],
            "likes": p["likes"] or 0,
            "views": p["views"] or 0,
            "bookmark_count": p["bookmark_count"],
            "preview": preview,
            "created_at": format_timestamp(p["created_at"]),
        })

    return render_template(
        "index.html",
        title="Feed",
        posts=formatted_posts
    )

# =========================================================
# POST PAGE
# =========================================================

@app.route("/post/<int:post_id>")
def post(post_id):

    try:

        post = query_db("""

            SELECT
                posts.*,
                users.username,
                users.avatar

            FROM posts

            JOIN users
            ON posts.user_id = users.id

            WHERE posts.id = ?

        """, (post_id,), one=True)

    if not post:
        return render_template("error.html",
            title="Not Found",
            message="Historical entry not found."
        ), 404

        execute_db(
            "UPDATE posts SET views = views + 1 WHERE id = ?",
            (post_id,)
        )

        post = dict(post)

        post["avatar"] = sanitize_avatar(
            post.get("avatar") or "👤"
        )

        post["created_at"] = format_timestamp(
            post.get("created_at")
        )

        post["likes"] = post.get("likes") or 0

        post["views"] = post.get("views") or 0

        post["speed"] = float(
            post.get("speed") or 1
        )

        parsed_dialogue = []

        if post["type"] == "dialogue":
            parsed_dialogue = parse_dialogue_script(
                post["content"]
            )

        related_posts = query_db("""

            SELECT
                id,
                title,
                type

            FROM posts

            WHERE language = ?
            AND id != ?

            ORDER BY RANDOM()

            LIMIT 4

        """, (post["language"], post_id))

        return render_template(
            "post.html",
            title=post["title"],
            post=post,
            parsed_dialogue=parsed_dialogue,
            related_posts=related_posts
        )

    except Exception:

        print(traceback.format_exc())

        return render_template(
            "apology.html",
            title="Error",
            message="Something went wrong while loading this historical record."
        ), 500

# =========================================================
# CREATE POST
# =========================================================

@app.route("/create", methods=["GET", "POST"])
@login_required
def create():

    if request.method == "GET":

        return render_template(
            "create.html",
            title="Create"
        )

    try:

        # =========================================
        # VERIFY USER STILL EXISTS
        # =========================================

        current_user = query_db(
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],),
            one=True
        )

        if not current_user:

            session.clear()

            return apology(
                "Session expired. Login again.",
                403
            )

        title = request.form.get(
            "title",
            ""
        ).strip()

        post_type = request.form.get(
            "type",
            ""
        ).strip()

        language = request.form.get(
            "language",
            "en-US"
        )

        content = request.form.get(
            "content",
            ""
        ).strip()

        speed_value = request.form.get(
            "speed",
            "1"
        )

        try:
            speed = float(speed_value)
        except:
            speed = 1.0

        speed = max(0.5, min(speed, 2.0))

        if not title:
            return apology("Title required", 400)

        if post_type not in [
            "dialogue",
            "audio",
            "read-only"
        ]:
            return apology("Invalid type", 400)

        if not validate_language(language):
            language = "en-US"

        filename = None

        # =========================================
        # DIALOGUE
        # =========================================

        if post_type == "dialogue":

            if not content:
                return apology(
                    "Dialogue content required",
                    400
                )

            parsed = parse_dialogue_script(content)

            if not parsed:
                return apology(
                    "Invalid dialogue format",
                    400
                )

        # =========================================
        # READ ONLY
        # =========================================

        if post_type == "read-only":

            if not content:
                return apology(
                    "Content required",
                    400
                )

        # =========================================
        # AUDIO
        # =========================================

        if post_type == "audio":

            file = request.files.get("audio")

            if not file:
                return apology(
                    "Audio file required",
                    400
                )

            if not allowed_audio_file(file.filename):

                return apology(
                    "Invalid audio file",
                    400
                )

            ext = file.filename.rsplit(".", 1)[1].lower()

            filename = f"{uuid.uuid4().hex}.{ext}"

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                secure_filename(filename)
            )

            file.save(filepath)

        # =========================================
        # INSERT POST
        # =========================================

        execute_db("""

            INSERT INTO posts (
                user_id,
                title,
                content,
                type,
                language,
                speed,
                audio_file
            )

            VALUES (?, ?, ?, ?, ?, ?, ?)

        """, (
            session["user_id"],
            title,
            content,
            post_type,
            language,
            speed,
            filename
        ))

        flash(
            "Historical entry published successfully.",
            "success"
        )

        return redirect("/")

    except Exception:

        print(traceback.format_exc())

        return render_template(
            "apology.html",
            title="Error",
            message="Publishing failed safely."
        ), 500

# =========================================================
# PROFILE (FIXED)
# =========================================================

@app.route("/profile/<username>")
def profile(username):

    user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

    if not user:
        return render_template("error.html",
            title="Not Found",
            message="User not found."
        ), 404

    posts = query_db("SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC", (user["id"],))

    bookmarks = query_db("""
        SELECT posts.*
        FROM bookmarks
        JOIN posts ON bookmarks.post_id = posts.id
        WHERE bookmarks.user_id = ?
    """, (user["id"],))

    stats = query_db("""
        SELECT COUNT(*) AS posts,
               COALESCE(SUM(likes),0) AS likes,
               COALESCE(SUM(views),0) AS views
        FROM posts
        WHERE user_id = ?
    """, (user["id"],), one=True)

    bookmark_count = query_db("SELECT COUNT(*) AS c FROM bookmarks WHERE user_id = ?", (user["id"],), one=True)

    user = dict(user)
    user["avatar"] = sanitize_avatar(user.get("avatar", ""))
    user["created_at"] = format_timestamp(user["created_at"])

    stats = dict(stats)
    stats["bookmarks"] = bookmark_count["c"]

    return render_template("profile.html",
        title=username,
        user=user,
        posts=posts,
        bookmarks=bookmarks,
        stats=stats
    )

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    if request.method == "GET":

        return render_template(
            "login.html",
            title="Login"
        )

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    ).strip()

    # =========================================
    # ADMIN LOGIN
    # =========================================

    if (
        username == ADMIN_USERNAME
        and password == ADMIN_PASSWORD
    ):

        session["user_id"] = -1
        session["username"] = "Developer"
        session["is_admin"] = True
        flash("Admin mode enabled", "success")
        return redirect("/")

    user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

    if not user:

        return apology(
            "Invalid credentials",
            403
        )

    if not check_password_hash(
        user["hash"],
        password
    ):

        return apology(
            "Invalid credentials",
            403
        )

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["is_admin"] = False

    return redirect("/")

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()
    flash("Logged out", "success")
    return redirect("/login")

# =========================================================
# ADMIN COMMAND SYSTEM
# =========================================================

@app.route("/admin/command", methods=["POST"])
@admin_required
def admin_command():

    command = request.json.get("command", "").strip()

    parts = command.split()
    action = parts[0].lower()

    try:

        if action == "ban_user":
            username = parts[1]
            execute_db("UPDATE users SET banned = 1 WHERE username = ?", (username,))
            return jsonify({"success": True})

        elif action == "unban_user":
            username = parts[1]
            execute_db("UPDATE users SET banned = 0 WHERE username = ?", (username,))
            return jsonify({"success": True})

        elif action == "delete_user_posts":
            username = parts[1]
            user = query_db("SELECT id FROM users WHERE username = ?", (username,), one=True)
            if not user:
                return jsonify({"success": False}), 404

            execute_db("DELETE FROM posts WHERE user_id = ?", (user["id"],))
            return jsonify({"success": True})

        return jsonify({"success": False, "error": "Unknown command"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# =========================================================
# API
# =========================================================

@app.route("/api/voices")
def api_voices():

    return jsonify({
        "voices": SUPPORTED_LANGUAGES
    })


@app.route("/api/post/<int:post_id>")
def api_post(post_id):

    post = query_db(
        "SELECT * FROM posts WHERE id = ?",
        (post_id,),
        one=True
    )

    if not post:
        return jsonify({"success": False}), 404

    return jsonify({"success": True, "post": dict(post)})

@app.route("/api/like/<int:post_id>", methods=["POST"])
@login_required
def like(post_id):

    execute_db(
        "UPDATE posts SET likes = likes + 1 WHERE id = ?",
        (post_id,)
    )

    row = query_db(
        "SELECT likes FROM posts WHERE id = ?",
        (post_id,),
        one=True
    )

    return jsonify({
        "likes": row["likes"]
    })


@app.route("/api/bookmark/<int:post_id>", methods=["POST"])
@login_required
def bookmark(post_id):

    existing = query_db("""

        SELECT id

        FROM bookmarks

        WHERE user_id = ?
        AND post_id = ?

    """, (
        session["user_id"],
        post_id
    ), one=True)

    if existing:

        execute_db(
            "DELETE FROM bookmarks WHERE id = ?",
            (existing["id"],)
        )

        return jsonify({
            "bookmarked": False
        })

    execute_db("INSERT INTO bookmarks (user_id, post_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
               (session["user_id"], post_id))

    return jsonify({
        "bookmarked": True
    })

# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def not_found(error):

    return render_template(
        "apology.html",
        title="404",
        message="Historical record not found."
    ), 404


@app.errorhandler(500)
def internal_error(error):

    print(traceback.format_exc())

    return render_template(
        "apology.html",
        title="500",
        message="The archive encountered a disruption."
    ), 500

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
