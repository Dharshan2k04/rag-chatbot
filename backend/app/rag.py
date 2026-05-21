from .embeddings import get_user_store
from .llm_hf import query_huggingface, stream_groq_response


def rag_answer(query: str, user_id: int, k: int = 4, temperature: float = 0.7,
               stream: bool = False, doc_ids: list[int] = None):
    """RAG pipeline: Retrieve and Generate for a specific user.
    
    If doc_ids is provided, search is restricted to those documents only.
    Otherwise searches across all of the user's indexed documents.
    """
    print(f"🔍 User {user_id} searching for: {query}")

    store = get_user_store(user_id)
    results = store.search(query, k=k, doc_ids=doc_ids)

    print(f"📚 Found {len(results)} results")

    if not results:
        print("❌ No documents in index!")
        raise ValueError("No documents found. Please upload documents first.")

    for i, r in enumerate(results, 1):
        print(f"  Chunk {i} (distance: {r.get('distance', 0):.3f}): {r['text'][:100]}...")

    context_parts = []
    for i, r in enumerate(results, 1):
        context_parts.append(f"[Source {i}]\n{r['text']}")

    context = "\n\n".join(context_parts)
    print(f"📄 Context length: {len(context)} characters")

    sources = [
        {
            "text": r["text"][:300] + "..." if len(r["text"]) > 300 else r["text"],
            "source": r["metadata"].get("source", "unknown"),
            "chunk_id": r["metadata"].get("chunk_id", 0),
            "doc_id": r["metadata"].get("doc_id"),
            "distance": r.get("distance", 0)
        }
        for r in results
    ]

    if stream:
        print(f"🤖 Generating streaming answer (temperature={temperature})...")
        return stream_groq_response(query, context, temperature=temperature), sources

    print(f"🤖 Generating answer (temperature={temperature})...")
    answer = query_huggingface(query, context, temperature=temperature, stream=False)
    return answer, sources