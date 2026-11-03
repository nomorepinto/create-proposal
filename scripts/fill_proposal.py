"""Copy a proposal template and fill its existing slots.

The output is a copy of the template .docx. Text is written into paragraphs
and cells that are already there. Extra lines are clones of a template
paragraph or table row. This script never builds a document from scratch.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
P = f"{W}p"
R = f"{W}r"
RPR = f"{W}rPr"
T = f"{W}t"
BR = f"{W}br"
B = f"{W}b"
VAL = f"{W}val"
TBL = f"{W}tbl"
TR = f"{W}tr"
TC = f"{W}tc"

ANSWER_KEYS = {"set_text", "replace_paragraphs", "rebuild_rows"}
ILLEGAL_FILENAME = '<>:"/\\|?*'


def register_namespaces(xml_bytes: bytes) -> None:
    for prefix, uri in re.findall(br'xmlns:([A-Za-z0-9]+)="([^"]+)"', xml_bytes):
        ET.register_namespace(prefix.decode(), uri.decode())


def paragraph_runs(paragraph: ET.Element) -> list[ET.Element]:
    runs = []
    for run in paragraph.findall(R):
        local_names = {child.tag.split("}")[-1] for child in run.iter()}
        if "drawing" in local_names or "pict" in local_names or "object" in local_names:
            continue
        runs.append(run)
    return runs


def run_is_bold(run: ET.Element) -> bool:
    properties = run.find(RPR)
    if properties is None:
        return False
    bold = properties.find(B)
    if bold is None:
        return False
    return bold.get(VAL) not in {"0", "false", "off"}


def set_run_lines(run: ET.Element, lines: list[str]) -> None:
    properties = run.find(RPR)
    for child in list(run):
        if child is not properties:
            run.remove(child)
    for index, line in enumerate(lines):
        if index:
            ET.SubElement(run, BR)
        text = ET.SubElement(run, T)
        if line[:1].isspace() or line[-1:].isspace() or line == "":
            text.set(XML_SPACE, "preserve")
        text.text = line


def set_paragraph_text(paragraph: ET.Element, text: str) -> None:
    lines = text.split("\n")
    runs = paragraph_runs(paragraph)
    if not runs:
        run = ET.SubElement(paragraph, R)
        set_run_lines(run, lines)
        return

    if len(lines) == 1 and len(runs) >= 2 and run_is_bold(runs[0]) and not run_is_bold(runs[1]):
        for separator in (" – ", " — ", " - "):
            if separator in text:
                head, tail = text.split(separator, 1)
                set_run_lines(runs[0], [head])
                set_run_lines(runs[1], [separator + tail])
                for extra in runs[2:]:
                    parent = extra.getparent() if hasattr(extra, "getparent") else paragraph
                    if extra in list(parent):
                        parent.remove(extra)
                return

    set_run_lines(runs[0], lines)
    for extra in runs[1:]:
        if extra in list(paragraph):
            paragraph.remove(extra)


def set_cell_paragraphs(cell: ET.Element, texts: list[str]) -> None:
    """Replace a cell's paragraphs, cloning the template's own paragraphs.

    Existing paragraphs keep their formatting in order. Further paragraphs
    cycle those same template paragraphs, so a repeated block such as name,
    position, and email keeps that pattern.
    """
    originals = cell.findall(P)
    if not originals:
        raise ValueError("A table cell has no paragraph to clone.")
    prototypes = [copy.deepcopy(paragraph) for paragraph in originals]
    for paragraph in originals:
        cell.remove(paragraph)
    if not texts:
        texts = [""]
    for index, text in enumerate(texts):
        paragraph = copy.deepcopy(prototypes[index % len(prototypes)])
        set_paragraph_text(paragraph, text)
        cell.append(paragraph)


def body_of(root: ET.Element) -> ET.Element:
    body = root.find(f"{W}body")
    if body is None:
        raise ValueError("The template has no document body.")
    return body


def paragraph_at(body: ET.Element, index: int) -> ET.Element:
    children = list(body)
    if index < 0 or index >= len(children) or children[index].tag != P:
        raise KeyError(f"p:{index}")
    return children[index]


def table_at(body: ET.Element, index: int) -> ET.Element:
    tables = [child for child in body if child.tag == TBL]
    if index < 0 or index >= len(tables):
        raise KeyError(f"t:{index}")
    return tables[index]


def cell_at(body: ET.Element, table_index: int, row_index: int, col_index: int) -> ET.Element:
    table = table_at(body, table_index)
    rows = table.findall(TR)
    if row_index < 0 or row_index >= len(rows):
        raise KeyError(f"t:{table_index},r:{row_index}")
    cells = rows[row_index].findall(TC)
    if col_index < 0 or col_index >= len(cells):
        raise KeyError(f"t:{table_index},r:{row_index},c:{col_index}")
    return cells[col_index]


def parse_paragraph_path(path: str) -> int:
    match = re.fullmatch(r"p:(\d+)", path)
    if not match:
        raise KeyError(path)
    return int(match.group(1))


def parse_cell_path(path: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"t:(\d+),r:(\d+),c:(\d+)", path)
    if not match:
        raise KeyError(path)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def cell_values(value: object, label: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ValueError(f"{label} must be a string or a list of strings.")


def require_dict(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object.")
    return value


def validate(body: ET.Element, answers: dict) -> None:
    unknown = set(answers) - ANSWER_KEYS
    if unknown:
        raise ValueError(f"Unknown answers keys: {', '.join(sorted(unknown))}")
    if not any(answers.get(key) for key in ANSWER_KEYS):
        raise ValueError("The answers file has no edits.")

    for item in answers.get("set_text", []):
        item = require_dict(item, "set_text entry")
        path = item.get("path")
        if not isinstance(path, str):
            raise ValueError("set_text.path is missing.")
        has_text = "text" in item
        has_paragraphs = "paragraphs" in item
        if has_text == has_paragraphs:
            raise ValueError(f"{path} needs exactly one of text or paragraphs.")
        if has_text and not isinstance(item["text"], str):
            raise ValueError(f"{path} text must be a string.")
        if has_paragraphs:
            cell_values(item["paragraphs"], path)
        if path.startswith("p:"):
            paragraph_at(body, parse_paragraph_path(path))
        else:
            cell_at(body, *parse_cell_path(path))

    ranges = []
    for item in answers.get("replace_paragraphs", []):
        item = require_dict(item, "replace_paragraphs entry")
        start = parse_paragraph_path(str(item.get("start")))
        end = parse_paragraph_path(str(item.get("end")))
        if start > end:
            raise ValueError(f"Range p:{start} through p:{end} is backwards.")
        children = list(body)
        for index in range(start, end + 1):
            if index >= len(children) or children[index].tag != P:
                raise KeyError(f"p:{index}")
        texts = item.get("texts")
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise ValueError(f"p:{start} texts must be a list of strings.")
        ranges.append((start, end))
    ranges.sort()
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] <= previous[1]:
            raise ValueError(f"Paragraph ranges overlap: p:{previous[0]}-p:{previous[1]} and p:{current[0]}-p:{current[1]}")

    for item in answers.get("rebuild_rows", []):
        item = require_dict(item, "rebuild_rows entry")
        table_path = item.get("table")
        match = re.fullmatch(r"t:(\d+)", str(table_path))
        if not match:
            raise KeyError(str(table_path))
        table = table_at(body, int(match.group(1)))
        rows = table.findall(TR)
        keep = item.get("keep_rows")
        if not isinstance(keep, list) or not keep or not all(isinstance(index, int) for index in keep):
            raise ValueError(f"{table_path} keep_rows must be a non-empty list of row indexes.")
        if keep != sorted(keep) or len(set(keep)) != len(keep):
            raise ValueError(f"{table_path} keep_rows must be strictly increasing.")
        if keep[-1] >= len(rows) or keep[0] < 0:
            raise ValueError(f"{table_path} keep_rows is outside the table.")
        new_rows = item.get("rows")
        if not isinstance(new_rows, list):
            raise ValueError(f"{table_path} rows must be a list.")
        for row in new_rows:
            row = require_dict(row, f"{table_path} row")
            clone_row = row.get("clone_row")
            if not isinstance(clone_row, int) or clone_row < 0 or clone_row >= len(rows):
                raise ValueError(f"{table_path} clone_row {clone_row} is outside the table.")
            values = row.get("cells")
            if not isinstance(values, list):
                raise ValueError(f"{table_path} clone_row {clone_row} is missing cells.")
            cell_count = len(rows[clone_row].findall(TC))
            if len(values) != cell_count:
                raise ValueError(
                    f"{table_path} clone_row {clone_row} has {cell_count} cells, but {len(values)} values were given."
                )
            for value in values:
                cell_values(value, f"{table_path} clone_row {clone_row}")


def apply_answers(root: ET.Element, answers: dict) -> None:
    body = body_of(root)

    for item in answers.get("set_text", []):
        path = item["path"]
        if path.startswith("p:"):
            paragraph = paragraph_at(body, parse_paragraph_path(path))
            set_paragraph_text(paragraph, item["text"])
        else:
            cell = cell_at(body, *parse_cell_path(path))
            if "paragraphs" in item:
                set_cell_paragraphs(cell, item["paragraphs"])
            else:
                set_cell_paragraphs(cell, [item["text"]])

    ranges = sorted(answers.get("replace_paragraphs", []), key=lambda item: parse_paragraph_path(item["start"]), reverse=True)
    for item in ranges:
        start = parse_paragraph_path(item["start"])
        end = parse_paragraph_path(item["end"])
        children = list(body)
        block = children[start : end + 1]
        prototype = copy.deepcopy(block[0])
        for paragraph in block:
            body.remove(paragraph)
        for offset, text in enumerate(item["texts"]):
            paragraph = copy.deepcopy(prototype)
            set_paragraph_text(paragraph, text)
            body.insert(start + offset, paragraph)

    for item in answers.get("rebuild_rows", []):
        table = table_at(body, int(item["table"].split(":")[1]))
        original_rows = table.findall(TR)
        snapshots = [copy.deepcopy(row) for row in original_rows]
        keep = set(item["keep_rows"])
        for index, row in enumerate(original_rows):
            if index not in keep:
                table.remove(row)
        remaining = table.findall(TR)
        anchor = remaining[-1]
        for spec in item["rows"]:
            clone = copy.deepcopy(snapshots[spec["clone_row"]])
            cells = clone.findall(TC)
            for cell, value in zip(cells, spec["cells"]):
                set_cell_paragraphs(cell, cell_values(value, "cell"))
            anchor_at = list(table).index(anchor) + 1
            table.insert(anchor_at, clone)
            anchor = clone


def serialize(root: ET.Element, original_xml: bytes) -> bytes:
    """Write document.xml, keeping the template's root declarations.

    ElementTree drops namespace declarations that the edited nodes do not use.
    The template root declares the namespaces Word already expects, so the
    saved file keeps that opening tag and replaces only the body.
    """
    original = original_xml.decode("utf-8")
    open_start = original.find("<w:document")
    open_end = original.find(">", open_start)
    if open_start == -1 or open_end == -1:
        raise ValueError("The template document has no w:document root.")
    generated = ET.tostring(root, encoding="unicode")
    gen_start = generated.find("<w:document")
    gen_end = generated.find(">", gen_start)
    if gen_start == -1 or gen_end == -1:
        raise ValueError("Serialized document has no w:document root.")
    merged = original[open_start : open_end + 1] + generated[gen_end + 1 :]
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n' + merged).encode("utf-8")


def write_docx(template: Path, dest: Path, document_xml: bytes) -> None:
    with zipfile.ZipFile(template) as source:
        entries = [(item, source.read(item.filename)) for item in source.infolist()]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w") as package:
        for item, data in entries:
            if item.filename == "word/document.xml":
                data = document_xml
            info = zipfile.ZipInfo(filename=item.filename, date_time=item.date_time)
            info.compress_type = item.compress_type
            info.external_attr = item.external_attr
            info.flag_bits = item.flag_bits
            package.writestr(info, data)


def format_short_name(token: str, short_name: str) -> str:
    short = " ".join(short_name.strip().split())
    if not any(character.isspace() for character in token):
        short = "".join(short.split())
    if token.isupper():
        short = short.upper()
    elif token.islower():
        short = short.lower()
    short = "".join(character for character in short if character not in ILLEGAL_FILENAME)
    return short.strip(" .")


def proposal_filename(example_filename: str, short_name: str) -> str:
    stem = Path(example_filename).stem
    if " - " not in stem:
        raise ValueError(f"Example filename {example_filename!r} has no ' - ' event token to replace.")
    prefix, token = stem.rsplit(" - ", 1)
    short = format_short_name(token, short_name)
    if not short:
        raise ValueError("Short name is empty after removing characters that cannot be in a file name.")
    return f"{prefix} - {short}.docx"


def available_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    number = 2
    while True:
        numbered = directory / f"{stem} {number}.docx"
        if not numbered.exists():
            return numbered
        number += 1


def same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def load_answers(path: Path) -> dict:
    try:
        answers = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Answers file is not valid JSON: {error}") from error
    if not isinstance(answers, dict):
        raise ValueError("Answers file must be a JSON object.")
    return answers


def fill(template: Path, answers: dict, dest: Path) -> None:
    if same_file(dest, template):
        raise ValueError("Refusing to overwrite the template.")
    with zipfile.ZipFile(template) as package:
        document = package.read("word/document.xml")
    register_namespaces(document)
    root = ET.fromstring(document)
    validate(body_of(root), answers)
    apply_answers(root, answers)
    write_docx(template, dest, serialize(root, document))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fill a copy of a proposal template.")
    parser.add_argument("--print-name", action="store_true", help="Print the output filename and exit.")
    parser.add_argument("--example", help="Example proposal filename used as the naming pattern.")
    parser.add_argument("--short-name", help="Event token that replaces the example's event token.")
    parser.add_argument("--template", type=Path, help="Template .docx to copy.")
    parser.add_argument("--answers", type=Path, help="JSON file of slot edits.")
    parser.add_argument("--out", type=Path, help="Exact output path. Skips the example filename rule.")
    parser.add_argument("--out-dir", type=Path, help="Directory for the file named from the example.")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    if args.print_name:
        if not args.example or not args.short_name:
            raise SystemExit("--print-name requires --example and --short-name.")
        print(proposal_filename(args.example, args.short_name))
        return

    if args.template is None or args.answers is None:
        raise SystemExit("Filling requires --template and --answers.")
    if not args.template.is_file():
        raise SystemExit(f"Template not found: {args.template}")
    if not args.answers.is_file():
        raise SystemExit(f"Answers file not found: {args.answers}")

    example = Path(args.example) if args.example else None
    if args.out is not None:
        dest = args.out
    else:
        if args.example is None or args.short_name is None or args.out_dir is None:
            raise SystemExit("Name the output with --out, or pass --example, --short-name, and --out-dir.")
        if not args.out_dir.is_dir():
            raise SystemExit(f"Output directory not found: {args.out_dir}")
        dest = available_path(args.out_dir, proposal_filename(args.example, args.short_name))

    protected = [args.template]
    if example is not None and example.exists():
        protected.append(example)
    for path in protected:
        if same_file(dest, path):
            raise SystemExit(f"Refusing to overwrite {path}.")

    try:
        fill(args.template, load_answers(args.answers), dest)
    except (KeyError, ValueError) as error:
        raise SystemExit(str(error))
    print(dest)


if __name__ == "__main__":
    main()
