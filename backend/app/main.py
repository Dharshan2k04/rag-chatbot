import os
import logging
import json
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .dependencies import limiter
from .database import init_db, get_db, record_document, update_document_chunks
from .dependencies import get_current_user
from .models import User
from .ingest import ingest_document_sync
from .file_validator import validate_pdf_file
from .chat_routes import router as chat_router
from .auth_routes import router as auth_router
from .embeddings import get_user_store

# ---------------- Logging Setup ---------------- #
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Structured JSON logger for production
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        return json.dumps(log_obj)

json_handler = logging.StreamHandler()
json_handler.setFormatter(JSONFormatter())
logger.addHandler(json_handler)

# ---------------- Sentry Setup ---------------- #
if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=1.0 if settings.is_production else 0.0,
    )
    logger.info("Sentry SDK initialized")

# Create directories
os.makedirs("data", exist_ok=True)

# ---------------- FastAPI App ---------------- #
app = FastAPI(title="RAG Document Intelligence API")

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------- Security Headers Middleware ---------------- #
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers[
    "Content-Security-Policy"
    ] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com;"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response

# ---------------- CORS - Locked to Frontend Domain ---------------- #
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    settings.frontend_url,
]
if settings.is_production:
    # In production, only allow the configured frontend URL
    pass
else:
    # Development: allow all local origins
    ALLOWED_ORIGINS.extend([
        "http://127.0.0.1:3000",
        "https://localhost:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)

# ---------------- Initialize Database ---------------- #
init_db()
logger.info("Database initialized")

from .embeddings import rehydrate_all_stores
rehydrate_all_stores()
logger.info("FAISS stores rehydrated")
# ---------------- Register Routers ---------------- #
app.include_router(auth_router)
app.include_router(chat_router)

# ---------------- Background Task ---------------- #
def _background_ingest(file_path: str, user_id: int, doc_id: int, chat_id: int | None = None):
    """
    Ingests document chunks into FAISS, updates chunk_count in DB,
    and — if a chat_id was provided — binds the document to that chat
    so subsequent queries in that chat only search this document.
    """
    try:
        chunks = ingest_document_sync(file_path, user_id, doc_id=doc_id)
        from .database import SessionLocal, set_chat_active_document
        db = SessionLocal()
        try:
            update_document_chunks(db, doc_id, user_id, chunks)
 
            # Bind the document to the chat that triggered the upload
            if chat_id:
                set_chat_active_document(db, chat_id, user_id, doc_id)
                logger.info(f"Chat {chat_id} active document set to doc {doc_id}")
 
            db.commit()
            logger.info(f"Ingestion complete: user={user_id} doc={doc_id} chunks={chunks}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Background ingestion failed: {e}")

# ---------------- Routes ---------------- #

@app.get("/")
async def root():
    return {"message": "RAG Document Intelligence API is running"}


@app.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    # chat_id is optional — frontend passes it so the upload auto-activates
    # the document for that specific chat session
    chat_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload and ingest a document. Pass chat_id to bind it to a chat session."""
    try:
        file_path, original_filename = await validate_pdf_file(file, current_user.id)
 
        file_size = os.path.getsize(file_path)
        doc = record_document(
            db,
            current_user.id,
            os.path.basename(file_path),
            original_filename,
            file_size,
            chunk_count=0,
        )
        db.commit()
 
        # Pass chat_id into background task so it can bind the doc after ingestion
        background_tasks.add_task(_background_ingest, file_path, current_user.id, doc.id, chat_id)
 
        logger.info(
            f"Upload accepted: user={current_user.id} doc={doc.id} "
            f"file={original_filename} chat={chat_id}"
        )
 
        return {
            "message": "Document uploaded. Ingestion in progress...",
            "document_id": doc.id,
            "filename": original_filename,
            "chunks": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List uploaded documents for the authenticated user"""
    from .database import get_user_documents
    docs = get_user_documents(db, current_user.id)
    return {
        "documents": [
            {
                "id": d.id,
                "filename": d.original_filename,
                "file_size": d.file_size,
                "chunk_count": d.chunk_count,
                "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            }
            for d in docs
        ]
    }


@app.get("/test/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    """Get statistics about indexed documents for the user"""
    try:
        store = get_user_store(current_user.id)
        return {
            "total_chunks_indexed": store.index.ntotal,
            "embedding_dimension": store.dimension,
            "model": "all-MiniLM-L6-v2",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "api": "running"}