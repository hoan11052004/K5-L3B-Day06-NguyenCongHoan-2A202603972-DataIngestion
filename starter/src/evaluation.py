"""Evaluate retrieved evidence and preserve per-query traces."""
import re
from typing import Any


def _normalize_for_match(text: str) -> str:
    """Normalize whitespace and lowercasing for fuzzy substring matching."""
    return re.sub(r"\s+", " ", text).strip().lower()


def is_evidence_in_hit(hit: dict[str, Any], gold_page: int, evidence_quote: str) -> bool:
    """Check whether the retrieved hit matches the gold page and contains the required evidence."""
    hit_page = hit.get("page")
    if hit_page != gold_page:
        return False

    hit_text_norm = _normalize_for_match(hit.get("text", ""))
    ev_norm = _normalize_for_match(evidence_quote)

    if ev_norm in hit_text_norm:
        return True

    # Check keyword overlap (at least 85% of meaningful tokens)
    ev_tokens = [w for w in ev_norm.split() if len(w) > 3]
    if ev_tokens:
        matched_tokens = sum(1 for t in ev_tokens if t in hit_text_norm)
        if matched_tokens / len(ev_tokens) >= 0.85:
            return True

    return False


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]], strategy: str = "A") -> dict[str, Any]:
    """Evaluate top-3 hits against gold page and evidence quote, generating a complete trace record."""
    gold_page = int(question["gold_page"])
    evidence_quote = question["evidence_quote"]

    hits_evaluation = []
    hit_at_1 = False
    evidence_hit_at_3 = False

    for idx, hit in enumerate(hits):
        is_hit = is_evidence_in_hit(hit, gold_page, evidence_quote)
        hits_evaluation.append({
            "rank": idx + 1,
            "chunk_id": hit.get("chunk_id"),
            "page": hit.get("page"),
            "score": hit.get("score"),
            "is_evidence_hit": is_hit,
            "section": hit.get("section") or hit.get("metadata", {}).get("section", ""),
            "text_snippet": hit.get("text", "")[:180] + "..." if len(hit.get("text", "")) > 180 else hit.get("text", "")
        })
        if idx == 0 and is_hit:
            hit_at_1 = True
        if is_hit:
            evidence_hit_at_3 = True

    return {
        "question_id": question["id"],
        "split": question["split"],
        "type": question["type"],
        "question": question["question"],
        "strategy": strategy,
        "filter_applied": question.get("filter") if strategy == "C" else None,
        "gold_page": gold_page,
        "gold_source_id": question.get("gold_source_id"),
        "evidence_quote": evidence_quote,
        "hit_at_1": hit_at_1,
        "evidence_hit_at_3": evidence_hit_at_3,
        "hits": hits_evaluation
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    summary: dict[str, Any] = {}

    for trace in traces:
        strat = trace["strategy"]
        split = trace["split"]

        if strat not in summary:
            summary[strat] = {
                "dev": {"total": 0, "hit1": 0, "hit3": 0},
                "test": {"total": 0, "hit1": 0, "hit3": 0},
                "all": {"total": 0, "hit1": 0, "hit3": 0}
            }

        summary[strat][split]["total"] += 1
        summary[strat]["all"]["total"] += 1

        if trace["hit_at_1"]:
            summary[strat][split]["hit1"] += 1
            summary[strat]["all"]["hit1"] += 1

        if trace["evidence_hit_at_3"]:
            summary[strat][split]["hit3"] += 1
            summary[strat]["all"]["hit3"] += 1

    result: dict[str, Any] = {}
    for strat, splits in summary.items():
        result[strat] = {}
        for sp, stats in splits.items():
            tot = stats["total"]
            h1 = stats["hit1"]
            h3 = stats["hit3"]
            result[strat][sp] = {
                "total": tot,
                "hit1_count": h1,
                "hit1_rate": round(h1 / tot, 4) if tot > 0 else 0.0,
                "hit3_count": h3,
                "hit3_rate": round(h3 / tot, 4) if tot > 0 else 0.0,
                "hit1_str": f"{h1}/{tot} ({round(h1/tot*100, 1)}%)" if tot > 0 else "0/0",
                "hit3_str": f"{h3}/{tot} ({round(h3/tot*100, 1)}%)" if tot > 0 else "0/0"
            }

    return result
