"""
Migration script — run once:
    cd backend
    python migrate.py

What it does:
  1. Adds `active_doc_id` column to the `chats` table
  2. Removes `active_doc_id` from `users` table if it exists
     (it was mistakenly placed there in a previous version)
"""

import sqlite3
import os

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./chats.db").replace("sqlite:///", "")

def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def run():
    print(f"📂 Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── 1. Add active_doc_id to chats ──────────────────────────────────────
    if not column_exists(cursor, "chats", "active_doc_id"):
        print("➕ Adding active_doc_id to chats table...")
        cursor.execute(
            "ALTER TABLE chats ADD COLUMN active_doc_id INTEGER REFERENCES documents(id)"
        )
        print("✅ chats.active_doc_id added")
    else:
        print("ℹ️  chats.active_doc_id already exists — skipping")

    # ── 2. Remove active_doc_id from users (if it was added there by mistake) ─
    # SQLite does not support DROP COLUMN before version 3.35.0.
    # We handle both cases gracefully.
    if column_exists(cursor, "users", "active_doc_id"):
        try:
            print("🧹 Removing active_doc_id from users table...")
            cursor.execute("ALTER TABLE users DROP COLUMN active_doc_id")
            print("✅ users.active_doc_id removed")
        except sqlite3.OperationalError:
            # SQLite < 3.35 — cannot drop columns; safe to leave it, it won't be used
            print("⚠️  SQLite version too old to drop columns — users.active_doc_id "
                  "left in place but will not be used by the application.")
    else:
        print("ℹ️  users.active_doc_id not present — nothing to remove")

    conn.commit()
    conn.close()
    print("\n🎉 Migration complete. You can now start the server.")

if __name__ == "__main__":
    run()