import os
import sqlite3
import uuid
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
# ADMIN CONFIG
# =========================================================

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "developer")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "historygod123")

# =========================================================
# APP CONFIG
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
# DATABASE HELPERS
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
# CONTEXT
# =========================================================

@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now().year,
        "logged_in": session.get("user_id") is not None,
        "current_user": {
            "id": session.get("user_id"),
            "username": session.get("username")
        }
    }

# =========================================================
# FEED
# =========================================================

@app.route("/")
def index():
    language_filter = request.args.get("lang")
    type_filter = request.args.get("type")
    search_query = request.args.get("search")

    sql = """
        SELECT posts.*, users.username, users.avatar,
        (
            SELECT COUNT(*) FROM bookmarks
            WHERE bookmarks.post_id = posts.id
        ) AS bookmark_count
        FROM posts
        JOIN users ON posts.user_id = users.id
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
        ORDER BY (posts.likes * 3 + posts.views * 0.25) DESC,
        posts.created_at DESC
    """

    posts = query_db(sql, params)

    formatted = []

    for p in posts:
        preview = ""

        if p["type"] == "dialogue":
            parsed = parse_dialogue_script(p["content"])
            if parsed:
                preview = parsed[0]["text"][:180]

        elif p["type"] == "read-only":
            preview = p["content"][:180]

        elif p["type"] == "audio":
            preview = "Audio narration ready to play."

        formatted.append({
            "id": p["id"],
            "title": p["title"],
            "username": p["username"],
            "avatar": sanitize_avatar(p["avatar"] if p["avatar"] else ""),
            "type": p["type"],
            "language": p["language"],
            "likes": p["likes"] or 0,
            "views": p["views"] or 0,
            "bookmark_count": p["bookmark_count"] or 0,
            "preview": preview,
            "created_at": format_timestamp(p["created_at"]),
        })

    return render_template("index.html", title="Feed", posts=formatted)

# =========================================================
# POST PAGE
# =========================================================

@app.route("/post/<int:post_id>")
def post(post_id):

    post = query_db("""
        SELECT posts.*, users.username, users.avatar
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    """, (post_id,), one=True)

    if not post:
        return render_template("error.html",
            title="Not Found",
            message="Historical entry not found."
        ), 404

    execute_db("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))

    post = dict(post)
    post["created_at"] = format_timestamp(post["created_at"])
    post["avatar"] = sanitize_avatar(post.get("avatar", ""))
    post["likes"] = post.get("likes") or 0
    post["views"] = post.get("views") or 0
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
        title=post["title"],
        post=post,
        parsed_dialogue=parsed,
        related_posts=related
    )

# =========================================================
# CREATE
# =========================================================

@app.route("/create", methods=["GET", "POST"])
@login_required
def create():

    if request.method == "GET":
        return render_template("create.html", title="Create")

    title = request.form.get("title", "").strip()
    post_type = request.form.get("type", "").strip()
    language = request.form.get("language", "en-US")
    content = request.form.get("content", "").strip()
    speed_value = request.form.get("speed", "1")

    try:
        speed = float(speed_value)
    except:
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
        if not content or not parse_dialogue_script(content):
            return apology("Invalid script", 400)

    if post_type == "read-only" and not content:
        return apology("Content required", 400)

    if post_type == "audio":
        file = request.files.get("audio")
        if not file or not allowed_audio_file(file.filename):
            return apology("Invalid audio", 400)

        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(filename))
        file.save(path)

    execute_db("""
        INSERT INTO posts (user_id, title, content, type, language, speed, audio_file)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session["user_id"], title, content, post_type, language, speed, filename))

    flash("Posted successfully", "success")
    return redirect("/")

# =========================================================
# PROFILE (FIXED)
# =========================================================

@app.route("/profile/<username>")
def profile(username):

    user = query_db(
        "SELECT * FROM users WHERE username = ?",
        (username,),
        one=True
    )

    if not user:
        return render_template("error.html",
            title="Not Found",
            message="User not found."
        ), 404

    user = dict(user)
    user["avatar"] = sanitize_avatar(user.get("avatar", ""))

    # SAFE created_at fallback
    user["created_at"] = format_timestamp(user.get("created_at") or datetime.now())

    # POSTS (safe)
    posts = query_db(
        "SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],)
    ) or []

    # BOOKMARKS (SAFE — NO CRASH IF TABLE MISSING)
    try:
        bookmarks = query_db("""
            SELECT posts.*
            FROM bookmarks
            JOIN posts ON bookmarks.post_id = posts.id
            WHERE bookmarks.user_id = ?
        """, (user["id"],)) or []
    except:
        bookmarks = []

    # STATS (safe fallback)
    stats = query_db("""
        SELECT 
            COUNT(*) AS posts,
            COALESCE(SUM(likes),0) AS likes,
            COALESCE(SUM(views),0) AS views
        FROM posts
        WHERE user_id = ?
    """, (user["id"],), one=True)

    if not stats:
        stats = {"posts": 0, "likes": 0, "views": 0}
    else:
        stats = dict(stats)

    # bookmark count safe
    try:
        bookmark_count = query_db(
            "SELECT COUNT(*) AS c FROM bookmarks WHERE user_id = ?",
            (user["id"],),
            one=True
        )
        stats["bookmarks"] = bookmark_count["c"] if bookmark_count else 0
    except:
        stats["bookmarks"] = 0

    return render_template(
        "profile.html",
        title=username,
        user=user,
        posts=posts,
        bookmarks=bookmarks,
        stats=stats
    )
# =========================================================
# AUTH (REGISTER FIX ADDED)
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html", title="Register")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return apology("Missing username or password", 400)

    existing = query_db(
        "SELECT id FROM users WHERE username = ?",
        (username,),
        one=True
    )

    if existing:
        return apology("Username already exists", 400)

    hash_pw = generate_password_hash(password)

    execute_db(
        "INSERT INTO users (username, hash, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (username, hash_pw)
    )

    flash("Account created!", "success")
    return redirect("/login")

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    if request.method == "GET":
        return render_template("login.html", title="Login")

    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["user_id"] = -1
        session["username"] = "Developer"
        session["is_admin"] = True
        return redirect("/")

    user = query_db(
        "SELECT * FROM users WHERE username = ?",
        (username,),
        one=True
    )

    if not user or not check_password_hash(user["hash"], password):
        return apology("Invalid credentials", 403)

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["is_admin"] = False

    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =========================================================
# API (UNCHANGED)
# =========================================================

@app.route("/api/voices")
def api_voices():
    return jsonify({"voices": SUPPORTED_LANGUAGES})

@app.route("/api/post/<int:post_id>")
def api_post(post_id):
    post = query_db("SELECT * FROM posts WHERE id = ?", (post_id,), one=True)
    if not post:
        return jsonify({"success": False}), 404
    return jsonify({"success": True, "post": dict(post)})

@app.route("/api/like/<int:post_id>", methods=["POST"])
@login_required
def like(post_id):
    execute_db("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    row = query_db("SELECT likes FROM posts WHERE id = ?", (post_id,), one=True)
    return jsonify({"likes": row["likes"]})

@app.route("/api/bookmark/<int:post_id>", methods=["POST"])
@login_required
def bookmark(post_id):

    existing = query_db("""
        SELECT id FROM bookmarks
        WHERE user_id = ? AND post_id = ?
    """, (session["user_id"], post_id), one=True)

    if existing:
        execute_db("DELETE FROM bookmarks WHERE id = ?", (existing["id"],))
        return jsonify({"bookmarked": False})

    execute_db("""
        INSERT INTO bookmarks (user_id, post_id, created_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    """, (session["user_id"], post_id))

    return jsonify({"bookmarked": True})

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
