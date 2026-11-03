"""Extract a proposal template or example into JSON.

A .docx becomes paragraph and table slots with stable paths.
A .pdf becomes page text. PDF extraction needs pypdf.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
P = f"{W}p"
T = f"{W}t"
TBL = f"{W}tbl"
TR = f"{W}tr"
TC = f"{W}tc"


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.iter(T)).strip()


def cell_paragraphs(cell: ET.Element) -> list[str]:
    return [paragraph_text(paragraph) for paragraph in cell.findall(P)]


def extract_docx(path: Path) -> dict:
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    body = root.find(f"{W}body")
    if body is None:
        raise SystemExit(f"{path} has no document body.")

    blocks: list[dict] = []
    table_index = 0
    for index, child in enumerate(list(body)):
        if child.tag == P:
            blocks.append(
                {"path": f"p:{index}", "type": "paragraph", "text": paragraph_text(child)}
            )
        elif child.tag == TBL:
            rows = []
            for row_index, row in enumerate(child.findall(TR)):
                cells = []
                for col_index, cell in enumerate(row.findall(TC)):
                    cells.append(
                        {
                            "col": col_index,
                            "path": f"t:{table_index},r:{row_index},c:{col_index}",
                            "paragraphs": cell_paragraphs(cell),
                        }
                    )
                rows.append({"row": row_index, "cells": cells})
            blocks.append({"path": f"t:{table_index}", "type": "table", "rows": rows})
            table_index += 1
    return {"kind": "docx", "file": str(path), "blocks": blocks}


def clean_pdf_text(text: str) -> str:
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.splitlines()]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return cleaned.strip()


def extract_pdf(path: Path) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("pypdf is required to read PDF examples. Install it with: pip install pypdf")

    reader = PdfReader(str(path))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            raw = page.extract_text() or ""
        pages.append({"page": number, "text": clean_pdf_text(raw)})
    return {"kind": "pdf", "file": str(path), "pages": pages}


def extract(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".pdf":
        return extract_pdf(path)
    raise SystemExit(f"Unsupported file type {suffix}. Use a .docx or a .pdf.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/extract_proposal.py <proposal.docx|proposal.pdf>")
    path = Path(sys.argv[1])
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")
    json.dump(extract(path), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
