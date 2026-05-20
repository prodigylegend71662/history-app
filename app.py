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

app = Flask(__name__, instance_relative_config=True)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "change_this_secret_before_production"
)

app.config["DATABASE"] = os.path.join(app.instance_path, "history.db")
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

os.makedirs(app.instance_path, exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =========================================================
# DATABASE
# =========================================================

def get_db():
    """Get or create SQLite database connection with safety settings."""

    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Safely close database connection after request."""

    db = g.pop("db", None)
    if db:
        db.close()


def query_db(query, args=(), one=False):
    """Execute a SELECT query safely."""

    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query, args=()):
    """Execute INSERT/UPDATE/DELETE query safely."""

    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

# =========================================================
# ADMIN DECORATOR
# =========================================================

def admin_required(f):
    """Protect routes requiring admin authentication."""

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
    """Inject global variables into all templates."""

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
# POST PAGE
# =========================================================

@app.route("/post/<int:post_id>")
def post(post_id):
    """Render individual post with full dialogue parsing and related posts."""

    try:

        # FIX #1: CRITICAL - Proper indentation inside try block
        post = query_db("""
            SELECT posts.*, users.username, users.avatar
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.id = ?
        """, (post_id,), one=True)

        # FIX #1: Now properly indented inside try block
        if not post:
            return render_template(
                "apology.html",
                title="Not Found",
                message="Historical entry not found.",
                top="404"
            ), 404

        # FIX #1: This code is now reachable (no longer after return)
        execute_db(
            "UPDATE posts SET views = views + 1 WHERE id = ?",
            (post_id,)
        )

        post = dict(post)
        post["avatar"] = sanitize_avatar(post.get("avatar") or "👤")
        post["created_at"] = format_timestamp(post.get("created_at"))
        post["likes"] = post.get("likes") or 0
        post["views"] = post.get("views") or 0

        try:
            post["speed"] = float(post.get("speed") or 1)
        except (ValueError, TypeError):
            post["speed"] = 1.0

        post["speed"] = max(0.5, min(post["speed"], 2.0))

        parsed_dialogue = []
        if post.get("type") == "dialogue":
            parsed_dialogue = parse_dialogue_script(post.get("content") or "")

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
            parsed_dialogue=parsed_dialogue,
            related_posts=related
        )

    except Exception as e:
        # FIX #11: Use proper exception clause instead of bare except
        print(traceback.format_exc())
        return render_template(
            "apology.html",
            title="Error",
            message="Internal error loading post"
        ), 500

# =========================================================
# CREATE POST
# =========================================================

@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Handle post creation for dialogue, audio, and read-only entries."""

    if request.method == "GET":
        return render_template(
            "create.html",
            title="Create",
        )

    try:
        current_user = query_db(
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],),
            one=True,
        )

        if not current_user:
            session.clear()
            return apology("Session expired. Login again.", 403)

        title = (request.form.get("title", "") or "").strip()
        post_type = (request.form.get("type", "") or "").strip()
        language = request.form.get("language", "en-US") or "en-US"
        content = (request.form.get("content", "") or "").strip()
        speed_value = request.form.get("speed", "1") or "1"

        try:
            speed = float(speed_value)
        except (ValueError, TypeError):
            speed = 1.0

        speed = max(0.5, min(speed, 2.0))

        if not title:
            return apology("Title required", 400)

        if post_type not in ["dialogue", "audio", "read-only"]:
            return apology("Invalid type", 400)

        if not validate_language(language):
            language = "en-US"

        filename = None

        if post_type == "dialogue":
            if not content:
                return apology("Dialogue content required", 400)

            parsed = parse_dialogue_script(content)
            if not parsed:
                return apology("Invalid dialogue format", 400)

        if post_type == "read-only" and not content:
            return apology("Content required", 400)

        if post_type == "audio":
            file = request.files.get("audio")
            if not file:
                return apology("Audio file required", 400)

            if not allowed_audio_file(file.filename):
                return apology("Invalid audio file", 400)

            ext = file.filename.rsplit(".", 1)[-1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                secure_filename(filename),
            )
            file.save(filepath)

        execute_db("""
            INSERT INTO posts (
                user_id,
                title,
                content,
                type,
                language,
                speed,
                audio_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            content,
            post_type,
            language,
            speed,
            filename,
        ))

        flash("Historical entry published successfully.", "success")
        return redirect("/")

    except Exception:
        print(traceback.format_exc())
        return render_template(
            "apology.html",
            title="Error",
            message="Publishing failed safely.",
        ), 500

# =========================================================
# PROFILE PAGE
# =========================================================

@app.route("/profile/<username>")
def profile(username):
    """Render user profile with posts, bookmarks, and stats."""

    # FIX #6: Validate user exists
    user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

    if not user:
        return render_template("apology.html",
            title="Not Found",
            message="User not found.",
            top="404"
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
    user["avatar"] = sanitize_avatar(user.get("avatar") or "👤")
    user["bio"] = user.get("bio") or ""
    user["created_at"] = format_timestamp(user.get("created_at") or "")

    # FIX #14: Safe dict access for stats
    stats = dict(stats) if stats else {"posts": 0, "likes": 0, "views": 0}
    stats["bookmarks"] = bookmark_count["c"] if bookmark_count else 0

    return render_template("profile.html",
        title=username,
        user=user,
        posts=posts,
        bookmarks=bookmarks,
        stats=stats
    )

# =========================================================
# REGISTRATION - FIX #2: ADDED MISSING ROUTE
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    """Handle user registration with password hashing."""

    if request.method == "GET":

        return render_template(
            "register.html",
            title="Register"
        )

    try:

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        confirmation = request.form.get(
            "confirmation",
            ""
        ).strip()

        # Validation
        if not username:
            return apology("Username required", 400)

        if not password:
            return apology("Password required", 400)

        if password != confirmation:
            return apology("Passwords must match", 400)

        if len(password) < 6:
            return apology("Password must be at least 6 characters", 400)

        # Check if user exists
        existing = query_db(
            "SELECT id FROM users WHERE username = ?",
            (username,),
            one=True
        )

        if existing:
            return apology("Username already taken", 400)

        # Create account with hashed password
        hash_value = generate_password_hash(password)

        execute_db("""

            INSERT INTO users (username, hash, avatar)

            VALUES (?, ?, ?)

        """, (username, hash_value, "👤"))

        # Log them in automatically
        user = query_db(
            "SELECT * FROM users WHERE username = ?",
            (username,),
            one=True
        )

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["is_admin"] = False

        flash("Account created successfully!", "success")

        return redirect("/")

    except Exception:

        print(traceback.format_exc())

        return apology("Registration failed", 500)

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login with session management."""

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
    """Clear session and redirect to login."""

    session.clear()
    flash("Logged out", "success")
    return redirect("/login")

# =========================================================
# ADMIN COMMAND SYSTEM
# =========================================================

@app.route("/admin/command", methods=["POST"])
@admin_required
def admin_command():
    """Admin command processor for moderation tasks."""

    data = request.get_json(silent=True) or {}
    command = (data.get("command") or "").strip()

    parts = command.split()
    action = parts[0].lower() if parts else ""

    try:

        if action == "delete_user_posts":
            
            if len(parts) < 2:
                return jsonify({"success": False, "error": "Username required"}), 400

            username = parts[1]
            user = query_db("SELECT id FROM users WHERE username = ?", (username,), one=True)
            
            if not user:
                return jsonify({"success": False, "error": "User not found"}), 404

            execute_db("DELETE FROM posts WHERE user_id = ?", (user["id"],))
            return jsonify({"success": True, "message": f"Deleted all posts by {username}"})

        elif action == "clear_bookmarks":
            
            if len(parts) < 2:
                return jsonify({"success": False, "error": "Username required"}), 400

            username = parts[1]
            user = query_db("SELECT id FROM users WHERE username = ?", (username,), one=True)
            
            if not user:
                return jsonify({"success": False, "error": "User not found"}), 404

            execute_db("DELETE FROM bookmarks WHERE user_id = ?", (user["id"],))
            return jsonify({"success": True, "message": f"Cleared all bookmarks by {username}"})

        else:
            return jsonify({"success": False, "error": "Unknown command"}), 400

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

# =========================================================
# API ENDPOINTS
# =========================================================

@app.route("/api/voices")
def api_voices():
    """Return list of supported languages and voices."""

    return jsonify({
        "voices": SUPPORTED_LANGUAGES
    })


@app.route("/api/post/<int:post_id>")
def api_post(post_id):
    """Return post data as JSON."""

    post = query_db(
        "SELECT * FROM posts WHERE id = ?",
        (post_id,),
        one=True
    )

    if not post:
        return jsonify({"success": False, "error": "Post not found"}), 404

    # FIX #7: Safe dict conversion with None checks
    post_dict = dict(post)
    post_dict["likes"] = post_dict.get("likes") or 0
    post_dict["views"] = post_dict.get("views") or 0
    post_dict["speed"] = post_dict.get("speed") or 1.0

    return jsonify({"success": True, "post": post_dict})

@app.route("/api/like/<int:post_id>", methods=["POST"])
@login_required
def like(post_id):
    """Increment like count on a post."""

    # Verify post exists
    post = query_db(
        "SELECT id FROM posts WHERE id = ?",
        (post_id,),
        one=True
    )

    if not post:
        return jsonify({"success": False, "error": "Post not found"}), 404

    execute_db(
        "UPDATE posts SET likes = likes + 1 WHERE id = ?",
        (post_id,)
    )

    row = query_db(
        "SELECT likes FROM posts WHERE id = ?",
        (post_id,),
        one=True
    )

    likes = row["likes"] if row else 0

    return jsonify({
        "success": True,
        "likes": likes
    })


@app.route("/api/bookmark/<int:post_id>", methods=["POST"])
@login_required
def bookmark(post_id):
    """Toggle bookmark status for a post."""

    # Verify post exists
    post = query_db(
        "SELECT id FROM posts WHERE id = ?",
        (post_id,),
        one=True
    )

    if not post:
        return jsonify({"success": False, "error": "Post not found"}), 404

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
            "success": True,
            "bookmarked": False
        })

    execute_db("INSERT INTO bookmarks (user_id, post_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
               (session["user_id"], post_id))

    return jsonify({
        "success": True,
        "bookmarked": True
    })

# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""

    return render_template(
        "apology.html",
        title="404",
        top="404",
        message="Historical record not found."
    ), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""

    print(traceback.format_exc())

    return render_template(
        "apology.html",
        title="500",
        top="500",
        message="The archive encountered a disruption."
    ), 500

# =========================================================
# MAIN - RENDER COMPATIBLE PORT HANDLING
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(
        debug=False,
        host="0.0.0.0",
        port=port,
    )
