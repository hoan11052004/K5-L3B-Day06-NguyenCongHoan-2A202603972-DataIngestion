"""Day 06: Data Ingestion Engineering Orchestrator.

Full pipeline implementation adhering to GUIDE.md and BENCHMARK.md.
"""
import json
import os
import time
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .store import PgVectorStore


def run_pipeline() -> dict[str, Any]:
    start_all_time = time.time()
    
    # Locate paths
    current_dir = Path(__file__).resolve().parent
    starter_dir = current_dir.parent
    root_dir = starter_dir.parent if (starter_dir.name == "starter") else starter_dir

    # Load environment variables
    load_dotenv(starter_dir / ".env")
    load_dotenv(root_dir / ".env")

    database_url = os.getenv("DATABASE_URL", "postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab")
    
    pdf_path = starter_dir / "data" / "dlbookvn_chap05.pdf"
    if not pdf_path.exists():
        pdf_path = root_dir / "data" / "dlbookvn_chap05.pdf"

    benchmark_path = root_dir / "benchmark" / "benchmark.json"
    if not benchmark_path.exists():
        benchmark_path = starter_dir / "data" / "benchmark.json"

    results_dir = starter_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / "results").mkdir(parents=True, exist_ok=True)

    print("==================================================================")
    print("STEP 1: Load and Validate Corpus")
    print("==================================================================")
    pages = load_pdf(pdf_path, document_id="dlbookvn-chap05", source="starter/data/dlbookvn_chap05.pdf")
    if len(pages) < 30:
        raise ValueError(f"Corpus does not meet the requirement of >=30 content pages! Got {len(pages)}")
    print(f"Validated corpus: {len(pages)} content pages loaded successfully.\n")

    print("==================================================================")
    print("STEP 2: Load Benchmark Questions")
    print("==================================================================")
    with open(benchmark_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    print(f"Loaded {len(questions)} questions (15 Dev / 5 Test).\n")

    print("==================================================================")
    print("STEP 3: Initialize Embedder & Vector Store")
    print("==================================================================")
    embedder = MyEmbedder()
    store = PgVectorStore(database_url=database_url, dimensions=embedder.dimensions)
    store.create_schema()
    print()

    print("==================================================================")
    print("STEP 4: Chunking and Ingestion for Strategies A, B, C")
    print("==================================================================")

    # Strategy A: Fixed-size 500, overlap 50
    t0 = time.time()
    chunks_a = []
    for p in pages:
        chunks_a.extend(fixed_size(p, size=500, overlap=50))
    time_chunk_a = time.time() - t0
    texts_a = [c.text for c in chunks_a]
    print(f"[Strategy A] Fixed-size: {len(chunks_a)} chunks created in {time_chunk_a:.2f}s")

    t0 = time.time()
    vectors_a = embedder.embed_documents(texts_a)
    time_embed_a = time.time() - t0
    store.upsert("A", chunks_a, vectors_a)
    total_time_a = time_chunk_a + time_embed_a
    print(f"[Strategy A] Embedded and stored in {total_time_a:.2f}s\n")

    # Strategy B: By-paragraph, max 800
    t0 = time.time()
    chunks_b = []
    for p in pages:
        chunks_b.extend(by_paragraph(p, max_size=800))
    time_chunk_b = time.time() - t0
    texts_b = [c.text for c in chunks_b]
    print(f"[Strategy B] By-paragraph: {len(chunks_b)} chunks created in {time_chunk_b:.2f}s")

    t0 = time.time()
    vectors_b = embedder.embed_documents(texts_b)
    time_embed_b = time.time() - t0
    store.upsert("B", chunks_b, vectors_b)
    total_time_b = time_chunk_b + time_embed_b
    print(f"[Strategy B] Embedded and stored in {total_time_b:.2f}s\n")

    # Strategy C: Same chunks and embeddings as Strategy B, stored with strategy C
    t0 = time.time()
    from .models import Chunk
    chunks_c = []
    for c in chunks_b:
        meta_c = dict(c.metadata)
        meta_c["strategy"] = "C"
        chunks_c.append(
            Chunk(
                chunk_id=c.chunk_id.replace("_pb", "_pc"),
                document_id=c.document_id,
                source=c.source,
                page=c.page,
                text=c.text,
                metadata=meta_c
            )
        )
    store.upsert("C", chunks_c, vectors_b)
    total_time_c = time_chunk_b + time_embed_b
    print(f"[Strategy C] Cloned B's chunks ({len(chunks_c)}) for controlled metadata filter comparison.\n")

    print("==================================================================")
    print("STEP 5: Benchmark Evaluation Across All Strategies")
    print("==================================================================")
    traces_a = []
    traces_b = []
    traces_c = []

    for q in questions:
        query_text = q["question"]
        q_vec = embedder.embed_query(query_text)

        # Strategy A: No filter
        hits_a = store.search("A", q_vec, top_k=3, filters=None)
        trace_a = evaluate_query(q, hits_a, strategy="A")
        traces_a.append(trace_a)

        # Strategy B: No filter
        hits_b = store.search("B", q_vec, top_k=3, filters=None)
        trace_b = evaluate_query(q, hits_b, strategy="B")
        traces_b.append(trace_b)

        # Strategy C: Apply filter if question has filter
        f_clause = q.get("filter")
        hits_c = store.search("C", q_vec, top_k=3, filters=f_clause)
        trace_c = evaluate_query(q, hits_c, strategy="C")
        traces_c.append(trace_c)

    # Save traces in both starter/results and root/results
    for dest in [results_dir, root_dir / "results"]:
        with open(dest / "traces_strategy_A.json", "w", encoding="utf-8") as f:
            json.dump(traces_a, f, ensure_ascii=False, indent=2)
        with open(dest / "traces_strategy_B.json", "w", encoding="utf-8") as f:
            json.dump(traces_b, f, ensure_ascii=False, indent=2)
        with open(dest / "traces_strategy_C.json", "w", encoding="utf-8") as f:
            json.dump(traces_c, f, ensure_ascii=False, indent=2)

    all_traces = traces_a + traces_b + traces_c
    summary = summarize(all_traces)

    for dest in [results_dir, root_dir / "results"]:
        with open(dest / "benchmark_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    stats = {
        "chunks_a": len(chunks_a),
        "chunks_b": len(chunks_b),
        "chunks_c": len(chunks_c),
        "time_a": round(total_time_a, 2),
        "time_b": round(total_time_b, 2),
        "time_c": round(total_time_c, 2),
        "summary": summary,
        "total_runtime": round(time.time() - start_all_time, 2)
    }

    print("==================================================================")
    print("STEP 6: Results Summary Table")
    print("==================================================================")
    print(f"{'Strategy':<10} | {'Split':<6} | {'Hit@1':<15} | {'Evidence Hit@3':<18} | {'Chunks':<8} | {'Time (s)':<10}")
    print("-" * 75)
    for strat in ["A", "B", "C"]:
        c_count = len(chunks_a) if strat == "A" else len(chunks_b)
        c_time = stats[f"time_{strat.lower()}"]
        for sp in ["dev", "test", "all"]:
            h1 = summary[strat][sp]["hit1_str"]
            h3 = summary[strat][sp]["hit3_str"]
            print(f"{strat:<10} | {sp:<6} | {h1:<15} | {h3:<18} | {c_count:<8} | {c_time:<10}")

    return stats


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
