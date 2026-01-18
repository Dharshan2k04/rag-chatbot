from .embeddings import embedding_store
from .llm import query_ollama

def rag_answer(query, k=2, temperature=0.7, stream=False):
    """RAG pipeline: Retrieve and Generate
    
    Optimized for speed-quality balance:
    - k=2 instead of 3 (faster retrieval, still good context)
    - Smaller context window
    - Streaming support
    """
    
    print(f"🔍 Searching for: {query}")
    
    # Retrieve relevant chunks (reduced from k=3 to k=2 for speed)
    results = embedding_store.search(query, k=k)
    
    print(f"📚 Found {len(results)} results")
    
    if not results:
        print("❌ No documents in index!")
        raise ValueError("No documents found. Please upload documents first.")
    
    # Combine context - optimized to be more concise
    context_parts = []
    for i, r in enumerate(results, 1):
        # Limit each chunk to 400 chars for speed
        text = r["text"][:400]
        context_parts.append(f"[{i}] {text}")
    
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
            "text": r["text"][:200] + "...",
            "source": r["metadata"].get("source", "unknown"),
            "chunk_id": r["metadata"].get("chunk_id", 0)
        }
        for r in results
    ]
    
    return answer, sources