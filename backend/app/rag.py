from .embeddings import embedding_store
from .llm import query_ollama

def rag_answer(query, k=4, temperature=0.7, stream=False):
    """RAG pipeline: Retrieve and Generate
    
    Optimized for accuracy:
    - k=4 for better context coverage (increased from 2)
    - Better prompt engineering
    - Full chunks without truncation
    """
    
    print(f"🔍 Searching for: {query}")
    
    # Retrieve relevant chunks (increased to k=4 for better accuracy)
    results = embedding_store.search(query, k=k)
    
    print(f"📚 Found {len(results)} results")
    
    if not results:
        print("❌ No documents in index!")
        raise ValueError("No documents found. Please upload documents first.")
    
    # Log retrieved chunks for debugging
    for i, r in enumerate(results, 1):
        print(f"  Chunk {i} (distance: {r.get('distance', 0):.3f}): {r['text'][:100]}...")
    
    # Combine context - use FULL chunks for accuracy
    context_parts = []
    for i, r in enumerate(results, 1):
        # Use full text without truncation
        text = r["text"]
        context_parts.append(f"[Source {i}]\n{text}")
    
    context = "\n\n".join(context_parts)
    print(f"📄 Context length: {len(context)} characters")
    
    # Generate answer with specified temperature
    print(f"🤖 Generating answer (temperature={temperature}, stream={stream})...")
    answer = query_ollama(query, context, temperature=temperature, stream=stream)
    
    if not stream:
        print(f"✅ Answer generated: {answer[:100] if isinstance(answer, str) else 'streaming'}...")
    
    # Return answer and sources
    sources = [
        {
            "text": r["text"][:300] + "..." if len(r["text"]) > 300 else r["text"],
            "source": r["metadata"].get("source", "unknown"),
            "chunk_id": r["metadata"].get("chunk_id", 0),
            "distance": r.get("distance", 0)
        }
        for r in results
    ]
    
    return answer, sources