from pypdf import PdfReader
from .embeddings import embedding_store
import os

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def chunk_text(text, chunk_size=1200, overlap=200):
    """Split text into chunks
    
    Optimized for accuracy (resumes, documents):
    - Larger chunks (1200) = better context preservation
    - More overlap (200) = don't split important info
    """
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        
        # Only add non-empty chunks
        if chunk.strip():
            chunks.append(chunk.strip())
        
        start += chunk_size - overlap
    
    return chunks

def ingest_document(file_path):
    """Process and store document - optimized for speed"""
    print(f"📄 Processing: {file_path}")
    
    # Extract text
    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    
    print(f"📝 Extracted {len(text)} characters")
    
    # Split into chunks (optimized size)
    chunks = chunk_text(text)
    print(f"✂️  Created {len(chunks)} chunks")
    
    # Create metadata
    filename = os.path.basename(file_path)
    metadatas = [{"text": chunk, "source": filename, "chunk_id": i} 
                 for i, chunk in enumerate(chunks)]
    
    # Add to FAISS (batch processing is automatic in our implementation)
    print(f"🔄 Embedding and indexing...")
    embedding_store.add_texts(chunks, metadatas)
    print(f"✅ Ingested {len(chunks)} chunks")
    
    return len(chunks)