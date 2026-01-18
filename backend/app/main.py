from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from .ingest import ingest_document
from .rag import rag_answer
from .database import init_db
from .chat_routes import router as chat_router

# Create data directory
os.makedirs("data", exist_ok=True)

# ✅ 1. Create FastAPI app
app = FastAPI(title="RAG Document Intelligence API")

# ✅ 2. Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 3. Initialize database
init_db()

# ✅ 4. Register routers
app.include_router(chat_router)

# ---------------- ROUTES ---------------- #

@app.get("/")
async def root():
    return {"message": "RAG Chatbot API is running"}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and ingest a document"""
    try:
        file_path = f"data/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        chunks_count = ingest_document(file_path)
        
        return {
            "message": "Document ingested successfully",
            "filename": file.filename,
            "chunks": chunks_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_documents(query: str):
    """Query documents (simple endpoint)"""
    try:
        answer, sources = rag_answer(query)
        return {
            "query": query,
            "answer": answer,
            "sources": sources
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))