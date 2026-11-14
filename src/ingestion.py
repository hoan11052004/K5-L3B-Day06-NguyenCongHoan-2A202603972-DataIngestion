"""Read and normalize source data. Fully implemented for Day 06."""
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Normalize Unicode NFC and clean whitespace while preserving paragraph structure."""
    if not text:
        return ""
    # Unicode NFC normalization
    text = unicodedata.normalize("NFC", text)
    # Remove zero-width spaces and BOM
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    # Normalize newline characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split paragraphs by 2 or more newlines
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned_paragraphs = []
    for para in paragraphs:
        lines = [line.strip() for line in para.split("\n") if line.strip()]
        if not lines:
            continue
        cleaned_para = " ".join(lines)
        cleaned_para = re.sub(r"[ \t]+", " ", cleaned_para).strip()
        if cleaned_para:
            cleaned_paragraphs.append(cleaned_para)
    return "\n\n".join(cleaned_paragraphs)


def _extract_section(p_text: str) -> str | None:
    """Detect section heading in page text."""
    matches = re.findall(r"(5\.\d+(?:\.\d+)?\s+[^\n]+)", p_text)
    if matches:
        for s in matches:
            s = s.strip()
            if len(s) < 45 and not any(k in s for k in ["Hình", "Bảng", "phương trình", "được gọi"]):
                return s
    return None


def load_pdf(path: Path, document_id: str = "dlbookvn-chap05", source: str = "starter/data/dlbookvn_chap05.pdf") -> list[DocumentPage]:
    """Extract each physical page; keep page number, source, section and metadata.

    Detects and excludes cover/TOC pages and empty pages.
    """
    pdf_path = Path(path)
    if not pdf_path.exists():
        # Try alternate path
        alt_path = Path("starter") / pdf_path
        if alt_path.exists():
            pdf_path = alt_path
        else:
            raise FileNotFoundError(f"PDF file not found: {path}")

    # Use pymupdf or pypdf
    pages: list[DocumentPage] = []
    try:
        import pymupdf
        doc = pymupdf.open(str(pdf_path))
        current_section = "5.0 Mục lục & Giới thiệu"
        for idx, page in enumerate(doc):
            p_num = idx + 1
            raw_text = page.get_text()
            norm_text = normalize_text(raw_text)

            # Skip first 2 pages (TOC/summary)
            if p_num <= 2:
                continue

            if len(norm_text) < 30:
                print(f"[Warning] Page {p_num} has minimal text ({len(norm_text)} chars); skipping.")
                continue

            sec = _extract_section(raw_text)
            if sec:
                current_section = sec

            metadata = {
                "section": current_section,
                "char_count": len(norm_text),
                "source_id": document_id
            }

            pages.append(
                DocumentPage(
                    document_id=document_id,
                    source=str(source),
                    page=p_num,
                    text=norm_text,
                    metadata=metadata
                )
            )
    except ImportError:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        current_section = "5.0 Mục lục & Giới thiệu"
        for idx, page in enumerate(reader.pages):
            p_num = idx + 1
            raw_text = page.extract_text() or ""
            norm_text = normalize_text(raw_text)

            if p_num <= 2 or len(norm_text) < 30:
                continue

            sec = _extract_section(raw_text)
            if sec:
                current_section = sec

            metadata = {
                "section": current_section,
                "char_count": len(norm_text),
                "source_id": document_id
            }

            pages.append(
                DocumentPage(
                    document_id=document_id,
                    source=str(source),
                    page=p_num,
                    text=norm_text,
                    metadata=metadata
                )
            )

    print(f"Loaded {len(pages)} valid content pages from {pdf_path}")
    return pages
