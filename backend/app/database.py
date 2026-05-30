"""SQLAlchemy database setup and helper functions"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, User, Chat, Message, Document

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chats.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully")


def get_db() -> Session:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== User Functions ====================

def create_user(db: Session, email: str, username: str, password_hash: str) -> User:
    """Create a new user"""
    user = User(
        email=email.lower(),
        username=username.lower(),
        password_hash=password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get user by email"""
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    """Get user by username"""
    return db.query(User).filter(User.username == username.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def update_failed_login_attempts(db: Session, user_id: int, increment: bool = True) -> User:
    """Update failed login attempts for account lockout"""
    user = get_user_by_id(db, user_id)
    if user:
        if increment:
            user.failed_login_attempts += 1
        else:
            user.failed_login_attempts = 0
        db.commit()
        db.refresh(user)
    return user


# ==================== Chat Functions ====================

def create_chat(db: Session, user_id: int, title: str = "New Chat") -> Chat:
    """Create a new chat session for a user"""
    chat = Chat(user_id=user_id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_chat_by_id(db: Session, chat_id: int, user_id: int) -> Chat | None:
    """Get chat by ID with user ownership verification"""
    return db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == user_id
    ).first()


def get_user_chats(db: Session, user_id: int) -> list[Chat]:
    """Get all chats for a user, ordered by most recent"""
    return db.query(Chat).filter(
        Chat.user_id == user_id
    ).order_by(Chat.updated_at.desc()).all()

def get_user_chats(db: Session, user_id: int, limit: int = 20, offset: int = 0) -> list[Chat]:
    """Get chats for a user with pagination, ordered by most recent"""
    return db.query(Chat).filter(
        Chat.user_id == user_id
    ).order_by(Chat.updated_at.desc()).limit(limit).offset(offset).all()


def get_user_chat_count(db: Session, user_id: int) -> int:
    """Get total number of chats for a user"""
    return db.query(Chat).filter(Chat.user_id == user_id).count()


def update_chat_title(db: Session, chat_id: int, user_id: int, title: str) -> Chat | None:
    """Update chat title with ownership verification"""
    chat = get_chat_by_id(db, chat_id, user_id)
    if chat:
        chat.title = title
        db.commit()
        db.refresh(chat)
    return chat


def delete_chat(db: Session, chat_id: int, user_id: int) -> bool:
    """Delete a chat with ownership verification"""
    chat = get_chat_by_id(db, chat_id, user_id)
    if chat:
        db.delete(chat)
        db.commit()
        return True
    return False


# ==================== Message Functions ====================

def save_message(db: Session, chat_id: int, user_id: int, role: str, message: str) -> Message:
    """Save a message to the database with user verification"""
    chat = get_chat_by_id(db, chat_id, user_id)
    if not chat:
        raise ValueError(f"Chat {chat_id} not found or does not belong to user {user_id}")

    msg = Message(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        message=message
    )
    db.add(msg)

    # FIX: flush first so the new msg gets a PK, THEN count existing user messages
    # Without flush(), count() sees the pending object and returns 1 instead of 0,
    # so the auto-title condition (== 0) never triggers.
    if role == "user":
        db.flush()  # <-- this is the only change in this function
        user_message_count = db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.role == "user"
        ).count()

        # Now count is 1 for the very first message (just flushed), so check == 1
        if user_message_count == 1:
            title = message[:50] + ("..." if len(message) > 50 else "")
            chat.title = title

    db.commit()
    db.refresh(msg)
    return msg

def get_chat_messages(db: Session, chat_id: int, user_id: int) -> list[Message]:
    """Get all messages for a chat with user ownership verification"""
    # Verify chat belongs to user
    chat = get_chat_by_id(db, chat_id, user_id)
    if not chat:
        raise ValueError(f"Chat {chat_id} not found or does not belong to user {user_id}")

    return db.query(Message).filter(
        Message.chat_id == chat_id
    ).order_by(Message.created_at).all()


# ==================== Document Functions ====================

def record_document(
    db: Session,
    user_id: int,
    filename: str,
    original_filename: str,
    file_size: int,
    chunk_count: int = 0
) -> Document:
    """Record a uploaded document in the database"""
    doc = Document(
        user_id=user_id,
        filename=filename,
        original_filename=original_filename,
        file_size=file_size,
        chunk_count=chunk_count
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def update_document_chunks(db: Session, doc_id: int, user_id: int, chunk_count: int) -> Document | None:
    """Update document chunk count after ingestion"""
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == user_id
    ).first()
    if doc:
        doc.chunk_count = chunk_count
        db.commit()
        db.refresh(doc)
    return doc


def get_user_documents(db: Session, user_id: int) -> list[Document]:
    """Get all documents for a user"""
    return db.query(Document).filter(
        Document.user_id == user_id
    ).order_by(Document.uploaded_at.desc()).all()


# ==================== Cleanup Functions ====================

def delete_all_data(db: Session):
    """WARNING: Delete all data from database (use only for testing)"""
    db.query(Message).delete()
    db.query(Document).delete()
    db.query(Chat).delete()
    db.query(User).delete()
    db.commit()


# ── PASTE THESE TWO FUNCTIONS into database.py ──────────────────────────────
# Add them in the "Chat Functions" section, after update_chat_title()
# Also replace your existing save_message() with the fixed version below.
# ─────────────────────────────────────────────────────────────────────────────


# ── REPLACEMENT for existing save_message() ───────────────────────────────────
def save_message(db: Session, chat_id: int, user_id: int, role: str, message: str) -> Message:
    """Save a message to the database with user verification"""
    chat = get_chat_by_id(db, chat_id, user_id)
    if not chat:
        raise ValueError(f"Chat {chat_id} not found or does not belong to user {user_id}")

    msg = Message(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        message=message
    )
    db.add(msg)

    if role == "user":
        # flush() writes the pending INSERT to the DB transaction so count()
        # sees it. Without this, count() returns 0 for the very first message
        # and the title-generation block below never fires.
        db.flush()
        user_message_count = db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.role == "user"
        ).count()

        if user_message_count == 1:   # first user message in this chat
            title = message[:50] + ("..." if len(message) > 50 else "")
            chat.title = title

    db.commit()
    db.refresh(msg)
    return msg


# ── NEW: set active document for a chat ───────────────────────────────────────
def set_chat_active_document(db: Session, chat_id: int, user_id: int, doc_id: int) -> Chat | None:
    """
    Bind a document to a chat session.
    All subsequent RAG queries on this chat will search only that document's chunks.
    Called automatically after a successful upload.
    """
    chat = get_chat_by_id(db, chat_id, user_id)
    if chat:
        chat.active_doc_id = doc_id
        db.commit()
        db.refresh(chat)
    return chat


# ── NEW: get active document ID for a chat ────────────────────────────────────
def get_chat_active_doc_id(db: Session, chat_id: int, user_id: int) -> int | None:
    """
    Return the doc_id that is currently active for this chat, or None if not set.
    chat_routes uses this to restrict FAISS search to a single document.
    """
    chat = get_chat_by_id(db, chat_id, user_id)
    return chat.active_doc_id if chat else None


def get_user_document_ids(db: Session, user_id: int) -> list[int]:
    """Get all document IDs for a user"""
    docs = db.query(Document).filter(
        Document.user_id == user_id,
        Document.chunk_count > 0  # Only documents that have been indexed
    ).all()
    return [doc.id for doc in docs]
