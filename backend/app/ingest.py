from pypdf import PdfReader
from .embeddings import get_user_store
import os


def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def chunk_text(text, chunk_size=1200, overlap=200):
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap

    return chunks


def ingest_document_sync(file_path: str, user_id: int, doc_id: int = None) -> int:
    """Process and store document for a specific user (synchronous, for BackgroundTask)"""
    print(f"📄 Processing for user {user_id}: {file_path}")

    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

    print(f"📝 Extracted {len(text)} characters")

    chunks = chunk_text(text)
    print(f"✂️  Created {len(chunks)} chunks")

    if not chunks:
        return 0

    filename = os.path.basename(file_path)
    metadatas = [
        {
            "text": chunk,
            "source": filename,
            "chunk_id": i,
            "user_id": user_id,
            "doc_id": doc_id  # Tag each chunk with its document ID
        }
        for i, chunk in enumerate(chunks)
    ]

    store = get_user_store(user_id)
    print(f"🔄 Embedding and indexing...")
    store.add_texts(chunks, metadatas, doc_id=doc_id)
    print(f"✅ Ingested {len(chunks)} chunks")

    return len(chunks)


def ingest_document(file_path: str, user_id: int = 0) -> int:
    return ingest_document_sync(file_path, user_id)