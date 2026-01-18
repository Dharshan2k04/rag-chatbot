import sqlite3
from datetime import datetime
import json

DB_PATH = "chats.db"

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id)
        )
    """)
    
    conn.commit()
    conn.close()

def create_chat():
    """Create a new chat session"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chats (title) VALUES (?)", ("New Chat",))
    chat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return chat_id

def update_chat_title(chat_id, title):
    """Update chat title based on first message"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (title, chat_id)
    )
    conn.commit()
    conn.close()

def save_message(chat_id, role, message):
    """Save a message to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Save message
    cursor.execute(
        "INSERT INTO messages (chat_id, role, message) VALUES (?, ?, ?)",
        (chat_id, role, message)
    )
    
    # Update chat timestamp
    cursor.execute(
        "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (chat_id,)
    )
    
    # Auto-generate title from first user message
    cursor.execute(
        "SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'user'",
        (chat_id,)
    )
    count = cursor.fetchone()[0]
    
    if count == 1 and role == "user":
        # Use first 50 chars of first message as title
        title = message[:50] + ("..." if len(message) > 50 else "")
        cursor.execute(
            "UPDATE chats SET title = ? WHERE id = ?",
            (title, chat_id)
        )
    
    conn.commit()
    conn.close()

def get_chat_messages(chat_id):
    """Get all messages for a chat"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, message, created_at FROM messages WHERE chat_id = ? ORDER BY created_at",
        (chat_id,)
    )
    messages = [
        {"role": row[0], "message": row[1], "created_at": row[2]}
        for row in cursor.fetchall()
    ]
    conn.close()
    return messages

def get_all_chats():
    """Get all chat sessions ordered by most recent"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, created_at, updated_at FROM chats ORDER BY updated_at DESC"
    )
    chats = [
        {
            "id": row[0], 
            "title": row[1], 
            "created_at": row[2],
            "updated_at": row[3]
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return chats

def delete_chat(chat_id):
    """Delete a chat and all its messages"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()