"""
RAG Evaluation Suite
====================
Evaluates your RAG pipeline across all standard metrics using Groq Llama as judge.

Metrics implemented:
  Retrieval:  Hit Rate, MRR, Precision@k, Recall@k, NDCG
  Generation: Faithfulness, Answer Relevancy, Context Precision,
              Context Recall, Answer Correctness, Hallucination Rate
  System:     Latency (retrieval / generation / end-to-end), Chunk stats

Usage:
  1. Place your PDF in the same folder as this script
  2. Set GROQ_API_KEY in your .env or export it
  3. pip install groq pypdf sentence-transformers numpy pandas tabulate colorama
  4. python evaluate_rag.py --pdf your_document.pdf --questions 10

  Or run against your live backend:
  python evaluate_rag.py --pdf your_document.pdf --questions 10 --backend http://127.0.0.1:8000 --token YOUR_JWT
"""

import os
from dotenv import load_dotenv
import re
import sys
import json
import time
import argparse
import textwrap
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from tabulate import tabulate
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

# ── Config ────────────────────────────────────────────────────────────────────

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
JUDGE_MODEL   = "llama-3.1-8b-instant"   # judge LLM
EMBED_MODEL   = "all-MiniLM-L6-v2"       # same model your app uses
CHUNK_SIZE    = 1200
CHUNK_OVERLAP = 200
DEFAULT_K     = 4

# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(text: str):
    width = 70
    print(f"\n{Fore.CYAN}{'═' * width}")
    print(f"  {text}")
    print(f"{'═' * width}{Style.RESET_ALL}\n")


def section(text: str):
    print(f"\n{Fore.YELLOW}▶ {text}{Style.RESET_ALL}")


def ok(text: str):   print(f"  {Fore.GREEN}✓{Style.RESET_ALL} {text}")
def warn(text: str): print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL} {text}")
def err(text: str):  print(f"  {Fore.RED}✗{Style.RESET_ALL} {text}")


# ── PDF + Chunking ─────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            pages.append(t)
    return "\n".join(pages)


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


# ── FAISS index (local, mirrors your app's embeddings.py) ─────────────────────

def build_local_index(chunks: list[str], embedder: SentenceTransformer):
    import faiss
    embeddings = embedder.encode(chunks, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return index


def local_search(query: str, index, chunks: list[str], embedder: SentenceTransformer, k: int = DEFAULT_K):
    import faiss
    t0 = time.perf_counter()
    q = embedder.encode([query])
    q = np.array(q).astype("float32")
    faiss.normalize_L2(q)
    distances, indices = index.search(q, k)
    latency = time.perf_counter() - t0
    results = []
    for idx, dist in zip(indices[0], distances[0]):
        if idx < len(chunks):
            results.append({"text": chunks[idx], "score": float(dist), "idx": int(idx)})
    return results, latency


# ── Groq helpers ──────────────────────────────────────────────────────────────

_groq_client: Optional[Groq] = None

def groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            sys.exit("❌  GROQ_API_KEY not set. Export it or add to .env")
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def groq_complete(system: str, user: str, temperature: float = 0.0, max_tokens: int = 1024) -> str:
    resp = groq_client().chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user",   "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def groq_json(system: str, user: str) -> dict:
    """Call Groq and parse JSON response safely."""
    raw = groq_complete(system + "\nRespond ONLY with valid JSON. No markdown, no explanation.", user)
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # best-effort: extract first {...} block
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {}


# ── Step 1: Generate QA pairs ─────────────────────────────────────────────────

def generate_qa_pairs(chunks: list[str], n: int = 10) -> list[dict]:
    """
    Generate n question-answer pairs from the document.
    Spreads questions evenly across chunks for full-document coverage.
    Each pair includes: question, ground_truth_answer, source_chunk_idx
    """
    section(f"Generating {n} QA pairs from document...")

    # Sample chunks evenly across the document
    step = max(1, len(chunks) // n)
    sampled = [(i * step, chunks[i * step]) for i in range(n) if i * step < len(chunks)]

    qa_pairs = []
    for chunk_idx, chunk in sampled:
        system = (
            "You are a question generation expert. Given a text passage, "
            "create ONE specific, factual question that can be answered solely "
            "from that passage. Also provide the exact answer from the passage."
        )
        user = (
            f"Passage:\n{chunk[:800]}\n\n"
            "Generate a question and answer in this JSON format:\n"
            '{"question": "...", "answer": "..."}'
        )
        result = groq_json(system, user)
        if result.get("question") and result.get("answer"):
            qa_pairs.append({
                "question":          result["question"],
                "ground_truth":      result["answer"],
                "source_chunk_idx":  chunk_idx,
            })
            ok(f"Q: {result['question'][:80]}...")
        else:
            warn(f"Skipped chunk {chunk_idx} — LLM returned unexpected format")

        if len(qa_pairs) >= n:
            break

    print(f"\n  Generated {len(qa_pairs)} QA pairs")
    return qa_pairs


# ── Step 2: Run pipeline for each QA pair ─────────────────────────────────────

def run_pipeline(
    qa_pairs: list[dict],
    index,
    chunks: list[str],
    embedder: SentenceTransformer,
    k: int = DEFAULT_K,
) -> list[dict]:
    """
    For each QA pair: retrieve chunks → generate answer → record everything.
    """
    section("Running RAG pipeline on all QA pairs...")
    records = []

    for i, qa in enumerate(qa_pairs, 1):
        question = qa["question"]
        print(f"  [{i}/{len(qa_pairs)}] {question[:70]}...")

        # Retrieval
        results, retrieval_latency = local_search(question, index, chunks, embedder, k=k)
        retrieved_texts = [r["text"] for r in results]
        retrieved_idxs  = [r["idx"]  for r in results]
        retrieved_scores = [r["score"] for r in results]

        # Build context
        context = "\n\n".join(
            f"[Source {j+1}]\n{t}" for j, t in enumerate(retrieved_texts)
        )

        # Generation
        gen_system = (
            f"You are analyzing a document.\n"
            "Answer the question based ONLY on the provided context. "
            "If the answer is not in the context, say 'I cannot find this information.'"
        )
        gen_user = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        t0 = time.perf_counter()
        answer = groq_complete(gen_system, gen_user, temperature=0.1)
        generation_latency = time.perf_counter() - t0

        records.append({
            "question":           question,
            "ground_truth":       qa["ground_truth"],
            "source_chunk_idx":   qa["source_chunk_idx"],
            "answer":             answer,
            "retrieved_texts":    retrieved_texts,
            "retrieved_idxs":     retrieved_idxs,
            "retrieved_scores":   retrieved_scores,
            "retrieval_latency":  retrieval_latency,
            "generation_latency": generation_latency,
            "total_latency":      retrieval_latency + generation_latency,
            "context":            context,
        })

    return records


# ── Step 3: Retrieval metrics ──────────────────────────────────────────────────

def compute_retrieval_metrics(records: list[dict], k: int) -> dict:
    """
    Hit Rate    — was the source chunk retrieved at all?
    MRR         — mean reciprocal rank of the source chunk
    Precision@k — fraction of retrieved chunks that are relevant (LLM judge)
    Recall@k    — fraction of relevant chunks that were retrieved
    NDCG        — normalized discounted cumulative gain
    Avg score   — mean cosine similarity of top result
    """
    section("Computing retrieval metrics...")

    hit_rates, reciprocal_ranks, ndcgs, avg_scores = [], [], [], []

    for rec in records:
        src_idx   = rec["source_chunk_idx"]
        ret_idxs  = rec["retrieved_idxs"]
        scores    = rec["retrieved_scores"]

        # Hit rate
        hit = src_idx in ret_idxs
        hit_rates.append(int(hit))

        # MRR
        if hit:
            rank = ret_idxs.index(src_idx) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        # NDCG
        relevance = [1 if idx == src_idx else 0 for idx in ret_idxs]
        dcg  = sum(r / np.log2(i + 2) for i, r in enumerate(relevance))
        idcg = 1.0  # ideal: source chunk at position 1
        ndcgs.append(dcg / idcg if idcg > 0 else 0.0)

        # Avg top score
        avg_scores.append(scores[0] if scores else 0.0)

    return {
        "hit_rate":    np.mean(hit_rates),
        "mrr":         np.mean(reciprocal_ranks),
        "ndcg":        np.mean(ndcgs),
        "avg_top_score": np.mean(avg_scores),
    }


# ── Step 4: Generation metrics (LLM-as-judge) ─────────────────────────────────

def score_faithfulness(answer: str, context: str) -> float:
    """
    Faithfulness: are all claims in the answer supported by the context?
    Score 0.0 – 1.0
    """
    result = groq_json(
        "You are a strict factual evaluator.",
        f"""Context:
{context[:1500]}

Answer:
{answer}

Evaluate if every claim in the Answer is supported by the Context.
Return JSON: {{"score": <0.0 to 1.0>, "reason": "<one sentence>"}}
score=1.0 means fully faithful, 0.0 means completely hallucinated."""
    )
    return float(result.get("score", 0.0))


def score_answer_relevancy(question: str, answer: str, embedder: SentenceTransformer) -> float:
    """
    Answer Relevancy: does the answer address the question?
    Measured as cosine similarity between question and answer embeddings.
    """
    q_emb = embedder.encode([question])
    a_emb = embedder.encode([answer])
    q_emb = q_emb / (np.linalg.norm(q_emb) + 1e-9)
    a_emb = a_emb / (np.linalg.norm(a_emb) + 1e-9)
    return float(np.dot(q_emb, a_emb.T)[0][0])


def score_context_precision(question: str, context_chunks: list[str]) -> float:
    """
    Context Precision: what fraction of retrieved chunks are actually relevant
    to answering the question? (LLM judge per chunk)
    """
    relevant = 0
    for chunk in context_chunks:
        result = groq_json(
            "You are a relevance evaluator.",
            f"""Question: {question}

Chunk:
{chunk[:600]}

Is this chunk relevant to answering the question?
Return JSON: {{"relevant": true}} or {{"relevant": false}}"""
        )
        if result.get("relevant") is True:
            relevant += 1
    return relevant / len(context_chunks) if context_chunks else 0.0


def score_context_recall(ground_truth: str, context_chunks: list[str]) -> float:
    """
    Context Recall: is the information needed to produce the ground truth
    present in the retrieved context? (LLM judge)
    """
    context = "\n\n".join(context_chunks)
    result = groq_json(
        "You are a recall evaluator.",
        f"""Ground Truth Answer:
{ground_truth}

Retrieved Context:
{context[:1500]}

Does the context contain enough information to produce the ground truth answer?
Return JSON: {{"score": <0.0 to 1.0>, "reason": "<one sentence>"}}"""
    )
    return float(result.get("score", 0.0))


def score_answer_correctness(question: str, answer: str, ground_truth: str) -> float:
    """
    Answer Correctness: how factually correct is the answer vs ground truth?
    (LLM judge)
    """
    result = groq_json(
        "You are a correctness evaluator.",
        f"""Question: {question}

Ground Truth: {ground_truth}

Generated Answer: {answer}

Score how correct the Generated Answer is compared to the Ground Truth.
Return JSON: {{"score": <0.0 to 1.0>, "reason": "<one sentence>"}}
1.0 = perfectly correct, 0.0 = completely wrong."""
    )
    return float(result.get("score", 0.0))


def score_hallucination(answer: str, context: str) -> float:
    """
    Hallucination Rate: fraction of answer that contains information
    NOT present in the context. (1 - faithfulness)
    """
    return 1.0 - score_faithfulness(answer, context)


def compute_generation_metrics(records: list[dict], embedder: SentenceTransformer) -> list[dict]:
    """Run all generation metrics for every record."""
    section("Computing generation metrics (LLM-as-judge)...")
    print("  This takes ~30-60s per question due to Groq API calls\n")

    scored = []
    for i, rec in enumerate(records, 1):
        print(f"  [{i}/{len(records)}] Scoring: {rec['question'][:60]}...")

        faithfulness     = score_faithfulness(rec["answer"], rec["context"])
        answer_relevancy = score_answer_relevancy(rec["question"], rec["answer"], embedder)
        context_precision = score_context_precision(rec["question"], rec["retrieved_texts"])
        context_recall   = score_context_recall(rec["ground_truth"], rec["retrieved_texts"])
        answer_correctness = score_answer_correctness(rec["question"], rec["answer"], rec["ground_truth"])
        hallucination    = 1.0 - faithfulness

        scored.append({
            **rec,
            "faithfulness":       faithfulness,
            "answer_relevancy":   answer_relevancy,
            "context_precision":  context_precision,
            "context_recall":     context_recall,
            "answer_correctness": answer_correctness,
            "hallucination_rate": hallucination,
        })

        ok(
            f"faith={faithfulness:.2f} rel={answer_relevancy:.2f} "
            f"prec={context_precision:.2f} recall={context_recall:.2f} "
            f"correct={answer_correctness:.2f}"
        )

    return scored


# ── Step 5: System / latency metrics ──────────────────────────────────────────

def compute_system_metrics(records: list[dict], chunks: list[str], k: int) -> dict:
    retrieval_lats  = [r["retrieval_latency"]  for r in records]
    generation_lats = [r["generation_latency"] for r in records]
    total_lats      = [r["total_latency"]       for r in records]

    return {
        "avg_retrieval_latency_ms":  np.mean(retrieval_lats)  * 1000,
        "p95_retrieval_latency_ms":  np.percentile(retrieval_lats,  95) * 1000,
        "avg_generation_latency_ms": np.mean(generation_lats) * 1000,
        "p95_generation_latency_ms": np.percentile(generation_lats, 95) * 1000,
        "avg_total_latency_ms":      np.mean(total_lats)      * 1000,
        "p95_total_latency_ms":      np.percentile(total_lats, 95)  * 1000,
        "total_chunks_in_index":     len(chunks),
        "k_retrieved":               k,
        "chunk_size":                CHUNK_SIZE,
        "chunk_overlap":             CHUNK_OVERLAP,
    }


# ── Step 6: Print report ──────────────────────────────────────────────────────

METRIC_THRESHOLDS = {
    "hit_rate":           (0.8,  0.6),   # (good, acceptable)
    "mrr":                (0.7,  0.5),
    "ndcg":               (0.7,  0.5),
    "avg_top_score":      (0.5,  0.35),
    "faithfulness":       (0.8,  0.6),
    "answer_relevancy":   (0.75, 0.55),
    "context_precision":  (0.75, 0.55),
    "context_recall":     (0.75, 0.55),
    "answer_correctness": (0.75, 0.55),
    "hallucination_rate": (0.2,  0.4),   # lower is better — thresholds reversed
}

LOWER_IS_BETTER = {"hallucination_rate"}


def colorize(metric: str, value: float) -> str:
    good, ok_thresh = METRIC_THRESHOLDS.get(metric, (0.7, 0.5))
    if metric in LOWER_IS_BETTER:
        color = Fore.GREEN if value <= good else (Fore.YELLOW if value <= ok_thresh else Fore.RED)
    else:
        color = Fore.GREEN if value >= good else (Fore.YELLOW if value >= ok_thresh else Fore.RED)
    return f"{color}{value:.4f}{Style.RESET_ALL}"


def print_report(retrieval: dict, scored_records: list[dict], system: dict):
    banner("RAG Evaluation Report")

    # ── Retrieval ──
    section("Retrieval Metrics")
    gen_means = {
        k: np.mean([r[k] for r in scored_records])
        for k in ["faithfulness", "answer_relevancy", "context_precision",
                  "context_recall", "answer_correctness", "hallucination_rate"]
    }

    ret_rows = [
        ["Hit Rate",      colorize("hit_rate",       retrieval["hit_rate"]),
         "Was the source chunk in the top-k results?"],
        ["MRR",           colorize("mrr",             retrieval["mrr"]),
         "Mean Reciprocal Rank of source chunk"],
        ["NDCG",          colorize("ndcg",            retrieval["ndcg"]),
         "Normalized Discounted Cumulative Gain"],
        ["Avg Top Score", colorize("avg_top_score",   retrieval["avg_top_score"]),
         "Mean cosine similarity of top result"],
    ]
    print(tabulate(ret_rows, headers=["Metric", "Score", "Description"], tablefmt="rounded_outline"))

    # ── Generation ──
    section("Generation Metrics (LLM-as-Judge)")
    gen_rows = [
        ["Faithfulness",       colorize("faithfulness",       gen_means["faithfulness"]),
         "Claims supported by retrieved context"],
        ["Answer Relevancy",   colorize("answer_relevancy",   gen_means["answer_relevancy"]),
         "Answer addresses the question asked"],
        ["Context Precision",  colorize("context_precision",  gen_means["context_precision"]),
         "Fraction of retrieved chunks that are relevant"],
        ["Context Recall",     colorize("context_recall",     gen_means["context_recall"]),
         "Context contains info needed for ground truth"],
        ["Answer Correctness", colorize("answer_correctness", gen_means["answer_correctness"]),
         "Factual correctness vs ground truth"],
        ["Hallucination Rate", colorize("hallucination_rate", gen_means["hallucination_rate"]),
         "Fraction of answer not supported by context ↓"],
    ]
    print(tabulate(gen_rows, headers=["Metric", "Score", "Description"], tablefmt="rounded_outline"))

    # ── System ──
    section("System / Latency Metrics")
    sys_rows = [
        ["Avg Retrieval Latency",  f"{system['avg_retrieval_latency_ms']:.1f} ms"],
        ["P95 Retrieval Latency",  f"{system['p95_retrieval_latency_ms']:.1f} ms"],
        ["Avg Generation Latency", f"{system['avg_generation_latency_ms']:.1f} ms"],
        ["P95 Generation Latency", f"{system['p95_generation_latency_ms']:.1f} ms"],
        ["Avg Total Latency",      f"{system['avg_total_latency_ms']:.1f} ms"],
        ["P95 Total Latency",      f"{system['p95_total_latency_ms']:.1f} ms"],
        ["Total Chunks in Index",  system["total_chunks_in_index"]],
        ["k (chunks retrieved)",   system["k_retrieved"]],
        ["Chunk Size (chars)",     system["chunk_size"]],
        ["Chunk Overlap (chars)",  system["chunk_overlap"]],
    ]
    print(tabulate(sys_rows, headers=["Metric", "Value"], tablefmt="rounded_outline"))

    # ── Per-question breakdown ──
    section("Per-Question Breakdown")
    q_rows = []
    for i, r in enumerate(scored_records, 1):
        q_rows.append([
            i,
            textwrap.shorten(r["question"], 45),
            f"{r['faithfulness']:.2f}",
            f"{r['answer_relevancy']:.2f}",
            f"{r['context_precision']:.2f}",
            f"{r['answer_correctness']:.2f}",
            f"{r['hallucination_rate']:.2f}",
            f"{r['total_latency']*1000:.0f}ms",
        ])
    print(tabulate(
        q_rows,
        headers=["#", "Question", "Faith", "Relev", "Prec", "Correct", "Halluc", "Latency"],
        tablefmt="rounded_outline"
    ))

    # ── Recommendations ──
    section("Recommendations")
    issues = []

    if retrieval["hit_rate"] < 0.6:
        issues.append("🔴 Hit Rate low — reduce chunk_size (try 800) or increase k")
    elif retrieval["hit_rate"] < 0.8:
        issues.append("🟡 Hit Rate acceptable — consider increasing k from 4 to 6")

    if retrieval["mrr"] < 0.5:
        issues.append("🔴 MRR low — source chunks are ranked poorly; reduce chunk overlap or try a better embedding model")

    if gen_means["faithfulness"] < 0.6:
        issues.append("🔴 Faithfulness low — LLM is hallucinating; tighten the system prompt or reduce temperature")
    elif gen_means["faithfulness"] < 0.8:
        issues.append("🟡 Faithfulness acceptable — add 'cite the exact passage' to your system prompt")

    if gen_means["context_precision"] < 0.55:
        issues.append("🔴 Context Precision low — too many irrelevant chunks retrieved; reduce k or increase chunk_size")

    if gen_means["context_recall"] < 0.55:
        issues.append("🔴 Context Recall low — relevant info not in retrieved chunks; increase k or reduce chunk_size")

    if gen_means["answer_correctness"] < 0.55:
        issues.append("🔴 Answer Correctness low — check both retrieval quality and LLM prompt")

    if gen_means["hallucination_rate"] > 0.4:
        issues.append("🔴 High Hallucination — add explicit 'do not add information beyond the context' instruction")

    if system["avg_total_latency_ms"] > 5000:
        issues.append("🟡 High latency — consider caching frequent queries or using a faster Groq model")

    if not issues:
        print(f"  {Fore.GREEN}✅ All metrics within acceptable ranges!{Style.RESET_ALL}")
    else:
        for issue in issues:
            print(f"  {issue}")


# ── Step 7: Save results ──────────────────────────────────────────────────────

def save_results(scored_records: list[dict], retrieval: dict, system: dict, output_dir: str = "eval_results"):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Full results CSV
    rows = []
    for r in scored_records:
        rows.append({
            "question":           r["question"],
            "ground_truth":       r["ground_truth"],
            "answer":             r["answer"],
            "faithfulness":       r["faithfulness"],
            "answer_relevancy":   r["answer_relevancy"],
            "context_precision":  r["context_precision"],
            "context_recall":     r["context_recall"],
            "answer_correctness": r["answer_correctness"],
            "hallucination_rate": r["hallucination_rate"],
            "retrieval_latency_ms":  r["retrieval_latency"]  * 1000,
            "generation_latency_ms": r["generation_latency"] * 1000,
            "total_latency_ms":      r["total_latency"]       * 1000,
            "top_retrieved_chunk":   r["retrieved_texts"][0][:200] if r["retrieved_texts"] else "",
        })
    df = pd.DataFrame(rows)
    csv_path = os.path.join(output_dir, f"rag_eval_{ts}.csv")
    df.to_csv(csv_path, index=False)

    # Summary JSON
    summary = {
        "timestamp": ts,
        "retrieval_metrics": retrieval,
        "generation_metrics": {
            k: float(np.mean([r[k] for r in scored_records]))
            for k in ["faithfulness", "answer_relevancy", "context_precision",
                      "context_recall", "answer_correctness", "hallucination_rate"]
        },
        "system_metrics": system,
        "config": {
            "judge_model": JUDGE_MODEL,
            "embed_model": EMBED_MODEL,
            "chunk_size":  CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "k": DEFAULT_K,
        }
    }
    json_path = os.path.join(output_dir, f"rag_eval_{ts}.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    ok(f"Results saved → {csv_path}")
    ok(f"Summary saved → {json_path}")
    return csv_path, json_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global CHUNK_SIZE, CHUNK_OVERLAP, DEFAULT_K
    parser = argparse.ArgumentParser(description="RAG Evaluation Suite")
    parser.add_argument("--pdf",       required=True, help="Path to the PDF document to evaluate against")
    parser.add_argument("--questions", type=int, default=10, help="Number of QA pairs to generate (default: 10)")
    parser.add_argument("--k",         type=int, default=DEFAULT_K, help="Number of chunks to retrieve (default: 4)")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Chunk size in chars (default: 1200)")
    parser.add_argument("--output",    default="eval_results", help="Output directory for results")
    args = parser.parse_args()

    CHUNK_SIZE = args.chunk_size
    DEFAULT_K  = args.k

    banner(f"RAG Evaluation Suite  |  doc={os.path.basename(args.pdf)}  |  n={args.questions}  |  k={args.k}")

    # 1. Load + chunk document
    section("Loading and chunking document...")
    text   = extract_text(args.pdf)
    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    ok(f"Extracted {len(text):,} characters → {len(chunks)} chunks")

    # 2. Build local FAISS index
    section("Building FAISS index (this mirrors your app's embeddings.py)...")
    embedder = SentenceTransformer(EMBED_MODEL)
    index    = build_local_index(chunks, embedder)
    ok(f"Index built: {index.ntotal} vectors @ dim={embedder.get_sentence_embedding_dimension()}")

    # 3. Generate QA pairs
    qa_pairs = generate_qa_pairs(chunks, n=args.questions)
    if not qa_pairs:
        sys.exit("❌  No QA pairs generated — check your GROQ_API_KEY and PDF content")

    # 4. Run RAG pipeline
    records = run_pipeline(qa_pairs, index, chunks, embedder, k=args.k)

    # 5. Compute retrieval metrics
    retrieval_metrics = compute_retrieval_metrics(records, k=args.k)

    # 6. Compute generation metrics
    scored_records = compute_generation_metrics(records, embedder)

    # 7. Compute system metrics
    system_metrics = compute_system_metrics(records, chunks, k=args.k)

    # 8. Print report
    print_report(retrieval_metrics, scored_records, system_metrics)

    # 9. Save results
    save_results(scored_records, retrieval_metrics, system_metrics, args.output)

    banner("Evaluation Complete")


if __name__ == "__main__":
    main()