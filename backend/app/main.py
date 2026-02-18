from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from .ingest import ingest_document
from .rag import rag_answer
from .database import init_db
from .chat_routes import router as chat_router
from .embeddings import embedding_store

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

# ---------------- DEBUG/TEST ENDPOINTS ---------------- #

@app.get("/test/search")
async def test_search(query: str, k: int = 5):
    """Test what chunks are being retrieved - useful for debugging hallucinations"""
    try:
        results = embedding_store.search(query, k=k)
        
        return {
            "query": query,
            "total_documents_indexed": embedding_store.index.ntotal,
            "chunks_retrieved": len(results),
            "results": [
                {
                    "chunk_id": r["metadata"].get("chunk_id", "unknown"),
                    "source": r["metadata"].get("source", "unknown"),
                    "distance": round(r.get("distance", 0), 3),
                    "text_preview": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                    "full_length": len(r["text"])
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test/stats")
async def get_stats():
    """Get statistics about indexed documents"""
    try:
        return {
            "total_chunks_indexed": embedding_store.index.ntotal,
            "total_metadata_entries": len(embedding_store.metadata),
            "embedding_dimension": embedding_store.dimension,
            "model": embedding_store.model.get_sentence_embedding_dimension()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test/clear")
async def clear_index():
    """Clear all indexed documents - useful for testing"""
    try:
        # Delete FAISS files
        if os.path.exists("faiss_index.bin"):
            os.remove("faiss_index.bin")
        if os.path.exists("metadata.pkl"):
            os.remove("metadata.pkl")
        
        # Reinitialize
        from .embeddings import EmbeddingStore
        global embedding_store
        embedding_store = EmbeddingStore()
        
        return {"message": "Index cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))