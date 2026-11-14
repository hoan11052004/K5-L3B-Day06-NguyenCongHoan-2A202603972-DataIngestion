"""Implement fixed-size and structure-aware chunking."""
import re
from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split text into overlapping windows of fixed character size and retain page metadata."""
    text = page.text
    if not text:
        return []

    chunks: list[Chunk] = []
    step = max(1, size - overlap)
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = min(start + size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunk_id = f"{page.document_id}_p{page.page}_fa{chunk_idx:03d}"
            meta = dict(page.metadata)
            meta["strategy"] = "A"
            meta["chunk_type"] = "fixed_size"
            meta["char_len"] = len(chunk_text)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=chunk_text,
                    metadata=meta,
                )
            )
            chunk_idx += 1
        if end >= len(text):
            break
        start += step

    return chunks


def _split_oversized_para(para: str, max_size: int) -> list[str]:
    """Split an oversized paragraph at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", para)
    parts: list[str] = []
    current_part = ""

    for sentence in sentences:
        if not sentence.strip():
            continue
        if len(current_part) + len(sentence) + 1 <= max_size:
            current_part = f"{current_part} {sentence}".strip() if current_part else sentence
        else:
            if current_part:
                parts.append(current_part)
            if len(sentence) > max_size:
                for i in range(0, len(sentence), max_size):
                    parts.append(sentence[i:i + max_size].strip())
                current_part = ""
            else:
                current_part = sentence
    if current_part:
        parts.append(current_part)
    return parts


def by_paragraph(page: DocumentPage, max_size: int = 800) -> list[Chunk]:
    """Group paragraphs, split oversized paragraphs cleanly, retaining context and metadata."""
    text = page.text
    if not text:
        return []

    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not raw_paragraphs:
        return []

    paragraphs: list[str] = []
    for p in raw_paragraphs:
        if len(p) <= max_size:
            paragraphs.append(p)
        else:
            paragraphs.extend(_split_oversized_para(p, max_size))

    chunks: list[Chunk] = []
    current_block: list[str] = []
    current_len = 0
    chunk_idx = 0

    for para in paragraphs:
        para_len = len(para)
        if current_block and (current_len + para_len + 2 > max_size):
            block_text = "\n\n".join(current_block).strip()
            chunk_id = f"{page.document_id}_p{page.page}_pb{chunk_idx:03d}"
            meta = dict(page.metadata)
            meta["strategy"] = "B"
            meta["chunk_type"] = "by_paragraph"
            meta["char_len"] = len(block_text)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=block_text,
                    metadata=meta,
                )
            )
            chunk_idx += 1
            current_block = [para]
            current_len = para_len
        else:
            current_block.append(para)
            current_len += para_len + 2

    if current_block:
        block_text = "\n\n".join(current_block).strip()
        chunk_id = f"{page.document_id}_p{page.page}_pb{chunk_idx:03d}"
        meta = dict(page.metadata)
        meta["strategy"] = "B"
        meta["chunk_type"] = "by_paragraph"
        meta["char_len"] = len(block_text)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=block_text,
                metadata=meta,
            )
        )

    return chunks
