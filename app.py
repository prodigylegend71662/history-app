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

DB_PATH = "instance/history.db"
app.config["DATABASE"] = DB_PATH
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs("instance", exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =========================================================
# AUTO DB INIT (FIX FOR RENDER)
# =========================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        hash TEXT,
        avatar TEXT,
        banned INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        content TEXT,
        type TEXT,
        language TEXT,
        likes INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0,
        speed REAL DEFAULT 1,
        audio_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        post_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

init_db()

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
# ROUTES
# =========================================================

@app.route("/")
def index():
    posts = query_db("SELECT * FROM posts ORDER BY created_at DESC")
    return render_template("index.html", posts=posts)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", title="Register")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return apology("Missing fields", 400)

    hash_pw = generate_password_hash(password)

    try:
        execute_db(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            (username, hash_pw)
        )
    except:
        return apology("Username already exists", 400)

    flash("Account created", "success")
    return redirect("/login")


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

    user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

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


@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "GET":
        return render_template("create.html")

    title = request.form.get("title")
    content = request.form.get("content")

    execute_db(
        "INSERT INTO posts (user_id, title, content, type, language) VALUES (?, ?, ?, ?, ?)",
        (session["user_id"], title, content, "read-only", "en")
    )

    return redirect("/")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
