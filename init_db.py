import os
import sqlite3

# =========================================================
# CONFIG
# =========================================================

DATABASE_PATH = "instance/history.db"

os.makedirs("instance", exist_ok=True)

# =========================================================
# CONNECTION
# =========================================================

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


connection = get_connection()
cursor = connection.cursor()

# =========================================================
# USERS TABLE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,

    avatar TEXT DEFAULT '👤',
    bio TEXT DEFAULT '',
    theme TEXT DEFAULT 'dark',
    pinned_post_id INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# POSTS TABLE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    title TEXT NOT NULL,
    content TEXT NOT NULL,

    type TEXT NOT NULL CHECK (
        type IN ('dialogue', 'audio', 'read-only')
    ),

    language TEXT DEFAULT 'en-US',

    likes INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,

    featured INTEGER DEFAULT 0,
    pinned INTEGER DEFAULT 0,

    audio_file TEXT,
    speed REAL DEFAULT 1,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
)
""")

# =========================================================
# BOOKMARKS TABLE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, post_id),

    FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY(post_id)
        REFERENCES posts(id)
        ON DELETE CASCADE
)
""")

# =========================================================
# COMMENTS TABLE (FUTURE)
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,

    content TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY(post_id)
        REFERENCES posts(id)
        ON DELETE CASCADE
)
""")

# =========================================================
# LIKES TABLE (FUTURE)
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, post_id),

    FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY(post_id)
        REFERENCES posts(id)
        ON DELETE CASCADE
)
""")

# =========================================================
# SAFE MIGRATION SYSTEM
# =========================================================

def add_column_if_missing(table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row["name"] for row in cursor.fetchall()]

    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"[MIGRATION] {table}.{column} added")


# =========================================================
# POSTS MIGRATIONS
# =========================================================

add_column_if_missing("posts", "speed", "REAL DEFAULT 1")

# =========================================================
# INDEXES (OPTIMIZED ORDER)
# =========================================================

def safe_index(name, sql):
    cursor.execute(f"DROP INDEX IF EXISTS {name}")
    cursor.execute(sql)

safe_index("idx_users_username",
           "CREATE INDEX idx_users_username ON users(username)")

safe_index("idx_posts_user",
           "CREATE INDEX idx_posts_user ON posts(user_id)")

safe_index("idx_posts_created",
           "CREATE INDEX idx_posts_created ON posts(created_at DESC)")

safe_index("idx_posts_type",
           "CREATE INDEX idx_posts_type ON posts(type)")

safe_index("idx_posts_language",
           "CREATE INDEX idx_posts_language ON posts(language)")

safe_index("idx_posts_views",
           "CREATE INDEX idx_posts_views ON posts(views DESC)")

safe_index("idx_posts_likes",
           "CREATE INDEX idx_posts_likes ON posts(likes DESC)")

safe_index("idx_bookmarks_user",
           "CREATE INDEX idx_bookmarks_user ON bookmarks(user_id)")

safe_index("idx_bookmarks_post",
           "CREATE INDEX idx_bookmarks_post ON bookmarks(post_id)")

safe_index("idx_comments_post",
           "CREATE INDEX idx_comments_post ON comments(post_id)")

safe_index("idx_likes_post",
           "CREATE INDEX idx_likes_post ON likes(post_id)")

# =========================================================
# COMMIT + CLOSE
# =========================================================

connection.commit()
connection.close()

# =========================================================
# STATUS OUTPUT
# =========================================================

print("\n======================================")
print(" HIS STORY OF HISTORY DB READY ")
print("======================================\n")

print("Database initialized successfully.")
print("Tables: users, posts, bookmarks, comments, likes")
print("Migrations applied safely.")
print("Indexes rebuilt.\n")

print("READY FOR FLASK + RENDER DEPLOYMENT 🚀")