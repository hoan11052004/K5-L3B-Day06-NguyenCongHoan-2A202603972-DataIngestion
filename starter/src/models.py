"""Shared data contracts; keep traceability from chunk back to source."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DocumentPage:
    document_id: str
    source: str
    page: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    source: str
    page: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalHit:
    chunk_id: str
    document_id: str
    source: str
    page: int
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkItem:
    id: str
    split: str
    type: str
    question: str
    expected_answer: str
    gold_source_id: str
    gold_page: int
    evidence_quote: str
    filter: Optional[dict[str, Any]] = None


@dataclass
class TraceRecord:
    question_id: str
    split: str
    type: str
    strategy: str
    question: str
    filter_applied: Optional[dict[str, Any]]
    hits: list[dict[str, Any]]
    hit_at_1: bool
    evidence_hit_at_3: bool
