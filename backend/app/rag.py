from .embeddings import get_user_store, get_reranker
from .llm_hf import query_huggingface, stream_groq_response


def _rerank_by_recency(results: list[dict], doc_ids: list[int] | None) -> list[dict]:
    """
    Re-rank FAISS results to boost chunks from the most recently uploaded document.

    FAISS ranks by cosine similarity alone — it has no concept of recency.
    When a user uploads BEL after Accenture and asks "what is this document about",
    Accenture chunks can outscore BEL chunks purely because the question is generic
    enough to match both. This re-ranker promotes chunks from the highest doc_id
    (most recently recorded in the DB, since IDs are auto-incremented) to the top,
    while preserving the original similarity order within each document group.

    Only activates when doc_ids is provided and contains more than one document.
    When searching a single document, FAISS order is already correct.
    """
    if not doc_ids or len(doc_ids) <= 1:
        return results  # nothing to re-rank

    # Most recently uploaded doc has the highest ID (auto-increment)
    most_recent_doc_id = max(doc_ids)

    recent = [r for r in results if r["metadata"].get("doc_id") == most_recent_doc_id]
    others = [r for r in results if r["metadata"].get("doc_id") != most_recent_doc_id]

    reranked = recent + others
    print(
        f"🔀 Re-ranked: {len(recent)} chunks from doc {most_recent_doc_id} "
        f"promoted above {len(others)} chunks from other docs"
    )
    return reranked


def _extract_filename(results: list[dict]) -> str | None:
    """
    Pull the source filename from the top result's metadata.
    This is passed to the LLM so it knows which document it is reading.
    Falls back to None if metadata is missing (LLM gets the base prompt).
    """
    for r in results:
        source = r.get("metadata", {}).get("source")
        if source:
            return source
    return None

def _rerank_with_cross_encoder(query: str, results: list[dict], top_k: int = 4) -> list[dict]:
    """
    Re-score candidates with a cross-encoder for true query-relevance.
    FAISS cosine similarity is a coarse filter; the cross-encoder reads
    the query and chunk together and scores actual relevance, which
    directly raises context precision and lowers hallucination.
    """
    if len(results) <= top_k:
        return results

    reranker = get_reranker()
    pairs = [[query, r["text"]] for r in results]
    scores = reranker.predict(pairs)

    for r, s in zip(results, scores):
        r["rerank_score"] = float(s)

    reranked = sorted(results, key=lambda r: r["rerank_score"], reverse=True)
    print(f"🎯 Cross-encoder reranked {len(results)} → top {top_k}")
    return reranked[:top_k]

def rag_answer(
    query: str,
    user_id: int,
    k: int = 4,
    temperature: float = 0.7,
    stream: bool = False,
    doc_ids: list[int] = None,
):
    """
    RAG pipeline: Retrieve → Re-rank → Generate for a specific user.

    doc_ids: if provided, FAISS search is filtered to only those documents.
             Re-ranking by recency is also applied when multiple docs are present.
    """
    print(f"🔍 User {user_id} searching: '{query}' | doc_ids={doc_ids}")

    store = get_user_store(user_id)
    results = store.search(query, k=k, doc_ids=doc_ids, rerank_pool=15)

    print(f"📚 Found {len(results)} results from FAISS")

    if not results:
        print("❌ No documents in index!")
        raise ValueError("No documents found. Please upload documents first.")

    # FIX 2: re-rank so chunks from the most recently uploaded doc come first
    # Step 1: cross-encoder reranking for true relevance (precision boost)
    results = _rerank_with_cross_encoder(query, results, top_k=k)
    # Step 2: recency boost when multiple docs present
    results = _rerank_by_recency(results, doc_ids)

    for i, r in enumerate(results, 1):
        print(
            f"  Chunk {i} | doc_id={r['metadata'].get('doc_id')} "
            f"| distance={r.get('distance', 0):.3f} | {r['text'][:80]}..."
        )

    # FIX 1: extract filename from top result to inject into the LLM system prompt
    filename = _extract_filename(results)
    print(f"📄 Active document for prompt: {filename or 'unknown'}")

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
            "distance": r.get("distance", 0),
        }
        for r in results
    ]

    if stream:
        print(f"🤖 Streaming answer | temperature={temperature} | doc={filename}")
        return (
            stream_groq_response(query, context, temperature=temperature, filename=filename),
            sources,
        )

    print(f"🤖 Generating answer | temperature={temperature} | doc={filename}")
    answer = query_huggingface(
        query, context, temperature=temperature, stream=False, filename=filename
    )
    return answer, sources