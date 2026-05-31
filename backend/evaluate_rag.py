"""
RAG Evaluation Suite — Option A (measures the REAL deployed pipeline)

Unlike the standalone version, this ingests the document through your actual
ingest_document_sync(), retrieves through your store.search() + cross-encoder
reranker, and generates answers through your real llm_hf.query_huggingface().
Every metric reflects the deployed system.

Run from the backend/ directory:
  python evaluate_rag_real.py --pdf your_document.pdf --questions 25
"""

import os
import re
import sys
import json
import time
import argparse
import textwrap
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer
from tabulate import tabulate
from colorama import Fore, Style, init as colorama_init

# ── Your actual pipeline ──
from app.embeddings import get_user_store, get_reranker
from app.rag import _rerank_with_cross_encoder, _rerank_by_recency
from app.ingest import ingest_document_sync, extract_text_from_pdf
from app.llm_hf import query_huggingface

load_dotenv()
colorama_init(autoreset=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
JUDGE_MODEL  = "llama-3.1-8b-instant"
EMBED_MODEL  = "all-MiniLM-L6-v2"
EVAL_USER_ID = 99999          # dedicated eval user, won't collide with real users
DEFAULT_K    = 4
RERANK_POOL  = 15
RERANK_THRESHOLD = 0.0   # cross-encoder logit cutoff; None disables filtering
import hashlib

def _qa_cache_path(pdf_path: str, n: int, cache_dir: str = "eval_qa_cache") -> str:
    """Deterministic cache filename keyed to the PDF content + question count."""
    os.makedirs(cache_dir, exist_ok=True)
    with open(pdf_path, "rb") as f:
        doc_hash = hashlib.sha256(f.read()).hexdigest()[:12]
    return os.path.join(cache_dir, f"qa_{doc_hash}_n{n}.json")


def load_or_generate_qa(stored_chunks, pdf_path, n, use_cache=True):
    """Load cached QA pairs if present, else generate and save them."""
    cache_path = _qa_cache_path(pdf_path, n)
    if use_cache and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            qa = json.load(f)
        ok(f"Loaded {len(qa)} cached QA pairs from {cache_path}")
        return qa

    qa = generate_qa_pairs(stored_chunks, n=n)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(qa, f, indent=2)
    ok(f"Cached {len(qa)} QA pairs → {cache_path}")
    return qa

# ── pretty printing ──
def banner(t):  print(f"\n{Fore.CYAN}{'═'*70}\n  {t}\n{'═'*70}{Style.RESET_ALL}\n")
def section(t): print(f"\n{Fore.YELLOW}▶ {t}{Style.RESET_ALL}")
def ok(t):      print(f"  {Fore.GREEN}✓{Style.RESET_ALL} {t}")
def warn(t):    print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL} {t}")

# ── Groq judge ──
_judge = None
def judge():
    global _judge
    if _judge is None:
        if not GROQ_API_KEY:
            sys.exit("❌ GROQ_API_KEY not set")
        _judge = Groq(api_key=GROQ_API_KEY)
    return _judge

def judge_complete(system, user, temperature=0.0, max_tokens=1024):
    r = judge().chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=temperature, max_tokens=max_tokens,
    )
    time.sleep(2) 
    return r.choices[0].message.content.strip()

def judge_json(system, user):
    raw = judge_complete(system + "\nRespond ONLY with valid JSON. No markdown.", user)
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except Exception: pass
    return {}

# ── Step 1: ingest through YOUR pipeline so chunk_ids align ──
def ingest_eval_doc(pdf_path):
    section("Ingesting document through the real pipeline...")
    store = get_user_store(EVAL_USER_ID)
    store.clear()  # fresh slate for this eval

    # write a temp copy ingest_document_sync can read
    n_chunks = ingest_document_sync(pdf_path, EVAL_USER_ID, doc_id=1)
    ok(f"Ingested {n_chunks} chunks under eval user {EVAL_USER_ID}")

    # pull the stored chunks + their chunk_ids straight from the store metadata
    stored = [
        {"chunk_id": m.get("chunk_id"), "text": m.get("text", "")}
        for m in store.metadata
    ]
    return store, stored

# ── Step 2: generate QA pairs keyed to stored chunk_ids ──
def generate_qa_pairs(stored_chunks, n=25):
    section(f"Generating {n} QA pairs aligned to stored chunks...")
    step = max(1, len(stored_chunks) // n)
    sampled = [stored_chunks[i*step] for i in range(n) if i*step < len(stored_chunks)]

    qa = []
    for ch in sampled:
        system = ("You are a question generation expert. Given a passage, create ONE "
                  "specific factual question answerable solely from it, plus the exact answer.")
        user = (f"Passage:\n{ch['text'][:800]}\n\n"
                'Return JSON: {"question": "...", "answer": "..."}')
        res = judge_json(system, user)
        if res.get("question") and res.get("answer"):
            qa.append({
                "question": res["question"],
                "ground_truth": res["answer"],
                "source_chunk_id": ch["chunk_id"],
            })
            ok(f"Q: {res['question'][:70]}...")
        if len(qa) >= n:
            break
    print(f"\n  Generated {len(qa)} QA pairs")
    return qa

# ── Step 3: run the REAL retrieval + generation ──
def run_pipeline(qa_pairs, store, k, use_rerank=True):

    section("Running the real reranked pipeline on all QA pairs...")
    records = []
    for i, qa in enumerate(qa_pairs, 1):
        q = qa["question"]
        print(f"  [{i}/{len(qa_pairs)}] {q[:65]}...")

        # ── retrieval through your store + cross-encoder, exactly like rag_answer ──
        t0 = time.perf_counter()
        results = store.search(q, k=RERANK_POOL if use_rerank else k, rerank_pool=RERANK_POOL)
        if use_rerank:
            results = _rerank_with_cross_encoder(
                q, results, top_k=k, score_threshold=RERANK_THRESHOLD
            )
        else:
            results = results[:k]
        results = _rerank_by_recency(results, doc_ids=None)
        retrieval_latency = time.perf_counter() - t0

        retrieved_texts  = [r["text"] for r in results]
        retrieved_ids    = [r["metadata"].get("chunk_id", -1) for r in results]
        retrieved_scores = [r.get("rerank_score", r.get("distance", 0.0)) for r in results]

        filename = results[0]["metadata"].get("source") if results else None
        context  = "\n\n".join(f"[Source {j+1}]\n{t}" for j, t in enumerate(retrieved_texts))

        # ── generation through YOUR llm_hf prompt ──
        t1 = time.perf_counter()
        answer = query_huggingface(q, context, temperature=0.1, filename=filename)
        generation_latency = time.perf_counter() - t1

        records.append({
            "question": q, "ground_truth": qa["ground_truth"],
            "source_chunk_id": qa["source_chunk_id"],
            "answer": answer,
            "retrieved_texts": retrieved_texts,
            "retrieved_ids": retrieved_ids,
            "retrieved_scores": retrieved_scores,
            "retrieval_latency": retrieval_latency,
            "generation_latency": generation_latency,
            "total_latency": retrieval_latency + generation_latency,
            "context": context,
        })
    return records

# ── Step 4: retrieval metrics (keyed on chunk_id) ──
def compute_retrieval_metrics(records):
    section("Computing retrieval metrics...")
    hits, rr, ndcg, top = [], [], [], []
    for rec in records:
        src = rec["source_chunk_id"]
        ids = rec["retrieved_ids"]
        scores = rec["retrieved_scores"]
        hit = src in ids
        hits.append(int(hit))
        if hit:
            rank = ids.index(src) + 1
            rr.append(1.0 / rank)
            rel = [1 if x == src else 0 for x in ids]
            dcg = sum(r / np.log2(i + 2) for i, r in enumerate(rel))
            ndcg.append(dcg / 1.0)
        else:
            rr.append(0.0); ndcg.append(0.0)
        top.append(scores[0] if scores else 0.0)
    return {
        "hit_rate": float(np.mean(hits)),
        "mrr": float(np.mean(rr)),
        "ndcg": float(np.mean(ndcg)),
        "avg_top_score": float(np.mean(top)),
    }

# ── Step 5: generation metrics (LLM-as-judge) ──
def score_faithfulness(answer, context):
    r = judge_json("You are a strict factual evaluator.",
        f"Context:\n{context[:1500]}\n\nAnswer:\n{answer}\n\n"
        'Are all claims supported? Return {"score": <0.0-1.0>}.')
    return float(r.get("score", 0.0))

def score_answer_relevancy(question, answer, embedder):
    qe = embedder.encode([question]); ae = embedder.encode([answer])
    qe = qe / (np.linalg.norm(qe) + 1e-9); ae = ae / (np.linalg.norm(ae) + 1e-9)
    return float(np.dot(qe, ae.T)[0][0])

def score_context_precision(question, chunks):
    if not chunks: return 0.0
    rel = 0
    for c in chunks:
        r = judge_json("You are a relevance evaluator.",
            f"Question: {question}\n\nChunk:\n{c[:600]}\n\n"
            'Is this chunk relevant? Return {"relevant": true} or {"relevant": false}.')
        if r.get("relevant") is True: rel += 1
    return rel / len(chunks)

def score_context_recall(ground_truth, chunks):
    ctx = "\n\n".join(chunks)
    r = judge_json("You are a recall evaluator.",
        f"Ground Truth:\n{ground_truth}\n\nContext:\n{ctx[:1500]}\n\n"
        'Does context contain enough to produce the ground truth? Return {"score": <0.0-1.0>}.')
    return float(r.get("score", 0.0))

def score_answer_correctness(question, answer, ground_truth):
    r = judge_json("You are a correctness evaluator.",
        f"Question: {question}\nGround Truth: {ground_truth}\nAnswer: {answer}\n\n"
        'Score correctness vs ground truth. Return {"score": <0.0-1.0>}.')
    return float(r.get("score", 0.0))

def compute_generation_metrics(records, embedder):
    section("Computing generation metrics (LLM-as-judge)...")
    scored = []
    for i, rec in enumerate(records, 1):
        print(f"  [{i}/{len(records)}] {rec['question'][:55]}...")
        faith = score_faithfulness(rec["answer"], rec["context"])
        scored.append({**rec,
            "faithfulness": faith,
            "answer_relevancy": score_answer_relevancy(rec["question"], rec["answer"], embedder),
            "context_precision": score_context_precision(rec["question"], rec["retrieved_texts"]),
            "context_recall": score_context_recall(rec["ground_truth"], rec["retrieved_texts"]),
            "answer_correctness": score_answer_correctness(rec["question"], rec["answer"], rec["ground_truth"]),
            "hallucination_rate": 1.0 - faith,
        })
    return scored

# ── Step 6: system metrics ──
def compute_system_metrics(records, store, k):
    rl = [r["retrieval_latency"] for r in records]
    gl = [r["generation_latency"] for r in records]
    tl = [r["total_latency"] for r in records]
    return {
        "avg_retrieval_latency_ms": float(np.mean(rl)*1000),
        "p95_retrieval_latency_ms": float(np.percentile(rl,95)*1000),
        "avg_generation_latency_ms": float(np.mean(gl)*1000),
        "p95_generation_latency_ms": float(np.percentile(gl,95)*1000),
        "avg_total_latency_ms": float(np.mean(tl)*1000),
        "p95_total_latency_ms": float(np.percentile(tl,95)*1000),
        "total_chunks_in_index": store.index.ntotal,
        "k_retrieved": k,
        "rerank_pool": RERANK_POOL,
    }

# ── Step 7: report + save ──
def print_report(retrieval, scored, system):
    banner("RAG Evaluation Report — REAL PIPELINE (with cross-encoder rerank)")
    gm = {k: float(np.mean([r[k] for r in scored])) for k in
          ["faithfulness","answer_relevancy","context_precision",
           "context_recall","answer_correctness","hallucination_rate"]}
    section("Retrieval Metrics")
    print(tabulate([
        ["Hit Rate", f"{retrieval['hit_rate']:.4f}"],
        ["MRR", f"{retrieval['mrr']:.4f}"],
        ["NDCG", f"{retrieval['ndcg']:.4f}"],
        ["Avg Top Score", f"{retrieval['avg_top_score']:.4f}"],
    ], headers=["Metric","Score"], tablefmt="rounded_outline"))
    section("Generation Metrics")
    print(tabulate([
        ["Faithfulness", f"{gm['faithfulness']:.4f}"],
        ["Answer Relevancy", f"{gm['answer_relevancy']:.4f}"],
        ["Context Precision", f"{gm['context_precision']:.4f}"],
        ["Context Recall", f"{gm['context_recall']:.4f}"],
        ["Answer Correctness", f"{gm['answer_correctness']:.4f}"],
        ["Hallucination Rate ↓", f"{gm['hallucination_rate']:.4f}"],
    ], headers=["Metric","Score"], tablefmt="rounded_outline"))
    section("System / Latency Metrics")
    print(tabulate([[k, v] for k, v in system.items()],
                   headers=["Metric","Value"], tablefmt="rounded_outline"))

def save_results(scored, retrieval, system, label="rerank", out="eval_results"):
    os.makedirs(out, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "timestamp": ts, "pipeline": "REAL (cross-encoder rerank)",
        "retrieval_metrics": retrieval,
        "generation_metrics": {k: float(np.mean([r[k] for r in scored])) for k in
            ["faithfulness","answer_relevancy","context_precision",
             "context_recall","answer_correctness","hallucination_rate"]},
        "system_metrics": system,
    }
    path = os.path.join(out, f"rag_eval_{label}_{ts}.json")
    with open(path, "w") as f: json.dump(summary, f, indent=2)
    ok(f"Saved → {path}")

# ── Main ──
def main():
    global DEFAULT_K, RERANK_THRESHOLD
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--questions", type=int, default=25)
    ap.add_argument("--k", type=int, default=DEFAULT_K)
    ap.add_argument("--qa-cache", action="store_true",
                    help="Reuse cached QA pairs for this PDF (required for valid A/B comparison)")
    ap.add_argument("--no-rerank", action="store_true",
                    help="Disable cross-encoder reranking (baseline run)")
    ap.add_argument("--rerank-threshold", type=float, default=0.0,
                    help="Cross-encoder score cutoff; chunks below are dropped (None-like: pass a very negative number to keep all)")
    args = ap.parse_args()

    RERANK_THRESHOLD = args.rerank_threshold
    DEFAULT_K = args.k

    banner(f"REAL Pipeline Eval | {os.path.basename(args.pdf)} | n={args.questions} | k={args.k}")

    store, stored = ingest_eval_doc(args.pdf)
    if not stored:
        sys.exit("❌ No chunks ingested")

    # warm up the reranker so its load time doesn't pollute latency stats
    section("Warming up cross-encoder...")
    get_reranker()
    ok("Reranker ready")

    qa = load_or_generate_qa(stored, args.pdf, args.questions, use_cache=args.qa_cache)
    if not qa:
        sys.exit("❌ No QA pairs generated")

    records   = run_pipeline(qa, store, k=args.k, use_rerank=not args.no_rerank)
    retrieval = compute_retrieval_metrics(records)
    embedder  = SentenceTransformer(EMBED_MODEL)
    scored    = compute_generation_metrics(records, embedder)
    system    = compute_system_metrics(records, store, k=args.k)

    print_report(retrieval, scored, system)
    save_results(scored, retrieval, system, label="baseline" if args.no_rerank else "rerank")
    banner("Evaluation Complete")

if __name__ == "__main__":
    main()