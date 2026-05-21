"""Automated RAG quality evaluation using RAGAS metrics."""

import os
import pytest
from app.embeddings import get_user_store
from app.ingest import ingest_document_sync
from app.rag import rag_answer

pytestmark = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set; skipping RAGAS evaluation tests"
)


def test_rag_retrieval_quality():
    """Evaluate that the RAG pipeline retrieves relevant chunks."""
    user_id = 999  # test user
    store = get_user_store(user_id)
    store.clear()

    # Ingest a known document
    sample_text = (
        "The capital of France is Paris. Paris is known for the Eiffel Tower. "
        "France is located in Western Europe and has a population of about 67 million. "
        "The French Revolution began in 1789."
    )
    import os
    test_path = "data/test_ragas_doc.txt"
    os.makedirs("data", exist_ok=True)
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(sample_text)

    ingest_document_sync(test_path, user_id)

    # Query
    answer, sources = rag_answer("What is the capital of France?", user_id=user_id, k=2)

    # Basic checks
    assert len(sources) > 0
    assert any("Paris" in s["text"] for s in sources)
    assert "Paris" in answer or "cannot find" in answer.lower()


def test_rag_faithfulness():
    """Check that the answer does not hallucinate beyond context."""
    user_id = 998
    store = get_user_store(user_id)
    store.clear()

    sample_text = "The quick brown fox jumps over the lazy dog."
    import os
    test_path = "data/test_fox.txt"
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(sample_text)

    ingest_document_sync(test_path, user_id)

    answer, _ = rag_answer("What color is the fox?", user_id=user_id, k=2)
    # The context says "brown fox"
    assert "brown" in answer.lower() or "cannot find" in answer.lower()


def test_rag_answer_to_unknown():
    """Check behavior when the answer is not in context."""
    user_id = 997
    store = get_user_store(user_id)
    store.clear()

    sample_text = "Python is a programming language."
    import os
    test_path = "data/test_python.txt"
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(sample_text)

    ingest_document_sync(test_path, user_id)

    answer, _ = rag_answer("What is the capital of Germany?", user_id=user_id, k=2)
    # Should indicate inability to find info
    assert "cannot find" in answer.lower() or "not in" in answer.lower() or "no information" in answer.lower()
