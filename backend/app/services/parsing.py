"""Convert uploaded documents to Markdown and chunk them for the LLM."""
from pathlib import Path
import re

CHUNK_CHARS = 8000        # ~2k tokens per chunk
CHUNK_OVERLAP = 400
MIN_CHUNK_CHARS = 300     # skip near-empty chunks
SUPPORTED_TYPES = {"pdf", "docx", "pptx", "epub", "md"}
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")


class ParseError(Exception):
    pass


def extract_text(path: str, filetype: str, max_pages: int) -> list[tuple[str, str]]:
    """Return list of (section_label, markdown_text)."""
    p = Path(path)
    if not p.exists():
        raise ParseError("Uploaded file is missing on disk")
    if filetype not in SUPPORTED_TYPES:
        raise ParseError(f"Unsupported file type: {filetype}")

    if filetype == "pdf":
        _validate_pdf_page_count(p, max_pages)

    markdown = (
        p.read_text(encoding="utf-8", errors="replace")
        if filetype == "md"
        else _convert_to_markdown(p)
    )
    return _markdown_sections(markdown)


def _convert_to_markdown(p: Path) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        raise ParseError("MarkItDown is not installed in the backend environment") from e

    try:
        converter = MarkItDown(enable_plugins=False)
        convert_local = getattr(converter, "convert_local", None)
        result = convert_local(str(p)) if convert_local else converter.convert(str(p))
        markdown = getattr(result, "text_content", None) or getattr(result, "markdown", None)
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Could not convert document to Markdown: {type(e).__name__}: {e}") from e

    markdown = _normalize_markdown(markdown or "")
    if not markdown:
        raise ParseError("No text found after converting document to Markdown")
    return markdown


def _validate_pdf_page_count(p: Path, max_pages: int):
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(p)
        page_count = doc.page_count
        doc.close()
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Could not inspect PDF page count: {type(e).__name__}: {e}") from e

    if page_count > max_pages:
        raise ParseError(f"PDF has {page_count} pages; max is {max_pages}")


def _normalize_markdown(markdown: str) -> str:
    lines = [line.rstrip() for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _markdown_sections(markdown: str) -> list[tuple[str, str]]:
    markdown = _normalize_markdown(markdown)
    if not markdown:
        raise ParseError("No text found in document")

    sections: list[tuple[str, str]] = []
    current_label = "document"
    buf: list[str] = []

    def flush():
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            sections.append((current_label, text))
        buf = []

    for line in markdown.splitlines():
        heading = HEADING_RE.match(line.strip())
        if heading:
            flush()
            current_label = heading.group(1).strip()[:80] or "section"
        buf.append(line)

    flush()
    if not sections:
        raise ParseError("No text found in document")
    return sections


def chunk_sections(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge/split sections into LLM-sized chunks, keeping a source label."""
    chunks = []
    buf_label, buf = None, ""
    for label, text in sections:
        if len(buf) + len(text) <= CHUNK_CHARS:
            buf_label = buf_label or label
            buf += ("\n\n" if buf else "") + text
        else:
            if buf and len(buf) >= MIN_CHUNK_CHARS:
                chunks.append((f"{buf_label}–{label}", buf))
            # split oversized single sections
            while len(text) > CHUNK_CHARS:
                chunks.append((label, text[:CHUNK_CHARS]))
                text = text[CHUNK_CHARS - CHUNK_OVERLAP:]
            buf_label, buf = label, text
    if buf and len(buf) >= MIN_CHUNK_CHARS:
        chunks.append((buf_label or "document", buf))
    if not chunks:
        raise ParseError("Document too short to generate cards from")
    return chunks
