import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf


class ParseError(Exception):
    pass


@dataclass
class Page:
    number: int  # 1-based
    paragraphs: list[str]


_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_WHITESPACE = re.compile(r"\s+")


def _clean_block(text: str) -> str:
    # Re-join words hyphenated across line breaks, then collapse layout whitespace.
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    return _WHITESPACE.sub(" ", text).strip()


def extract_pages(path: Path) -> list[Page]:
    """Extract text page by page, using PyMuPDF's layout blocks as paragraph boundaries.

    Keeping page numbers lets every chunk, and therefore every citation, point back to a page.
    """
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # pymupdf raises several exception types for corrupt files
        raise ParseError(f"Could not open PDF: {exc}") from exc

    with doc:
        if doc.needs_pass:
            raise ParseError("PDF is password-protected.")
        pages: list[Page] = []
        for index, page in enumerate(doc):
            blocks = page.get_text("blocks", sort=True)
            # block tuple: (x0, y0, x1, y1, text, block_no, block_type); type 0 = text, 1 = image
            paragraphs = [_clean_block(b[4]) for b in blocks if b[6] == 0]
            pages.append(Page(number=index + 1, paragraphs=[p for p in paragraphs if p]))
    return pages
