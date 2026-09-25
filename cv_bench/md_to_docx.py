"""Render a speaker-notes markdown file as a .docx with a navigable contents list.

Headings become real Word heading styles, so Word's navigation pane and the PDF
bookmark tree both work. Each heading also gets a bookmark, and a contents list
at the top links to them, so the document is clickable as well as navigable.

    python -m cv_bench.md_to_docx <in.md> <out.docx> [--image path=caption ...]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

INK = RGBColor(0x1A, 0x1A, 0x1A)
LINK = RGBColor(0x1F, 0x4E, 0x79)


def slug(text: str) -> str:
    return "s" + re.sub(r"[^A-Za-z0-9]", "", text)[:36]


def bookmark(par, name: str) -> None:
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(abs(hash(name)) % 100000))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(abs(hash(name)) % 100000))
    par._p.insert(0, start)
    par._p.append(end)


def link_to(par, anchor: str, text: str) -> None:
    h = OxmlElement("w:hyperlink")
    h.set(qn("w:anchor"), anchor)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F4E79")
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(color)
    rPr.append(u)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    h.append(r)
    par._p.append(h)


def emit_runs(par, text: str) -> None:
    """Bold for **x**, monospace for `x`."""
    for piece in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            r = par.add_run(piece[2:-2]); r.bold = True
        elif piece.startswith("`") and piece.endswith("`"):
            r = par.add_run(piece[1:-1]); r.font.name = "Consolas"; r.font.size = Pt(10)
        else:
            r = par.add_run(piece)
        r.font.color.rgb = INK


def build(md: Path, out: Path, images=None) -> None:
    lines = md.read_text().splitlines()
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11.5)
    st.paragraph_format.space_after = Pt(8)
    st.paragraph_format.line_spacing = 1.25

    title = next((l[2:] for l in lines if l.startswith("# ")), md.stem)
    h = doc.add_heading(title, level=0)
    for r in h.runs:
        r.font.color.rgb = INK

    tops = [(l[3:].strip(), slug(l[3:].strip())) for l in lines if l.startswith("## ")]
    c = doc.add_paragraph()
    c.add_run("Contents").bold = True
    for text, anc in tops:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(2)
        link_to(p, anc, text)
    doc.add_page_break()

    img = dict(images or {})
    table, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|"):
            table.append(line)
            i += 1
            if i < len(lines) and lines[i].startswith("|"):
                continue
            rows = [[c.strip() for c in r.strip("|").split("|")] for r in table
                    if not re.match(r"^\|[\s:-]+\|$", r)]
            if rows:
                t = doc.add_table(rows=len(rows), cols=len(rows[0]))
                t.style = "Light Grid Accent 1"
                for ri, row in enumerate(rows):
                    for ci, cell in enumerate(row[: len(rows[0])]):
                        para = t.cell(ri, ci).paragraphs[0]
                        emit_runs(para, cell)
                        para.paragraph_format.space_after = Pt(2)
                        for r in para.runs:
                            r.font.size = Pt(9.5)
                            if ri == 0:
                                r.bold = True
            doc.add_paragraph()
            table = []
            continue
        if line.startswith("# "):
            i += 1
            continue
        if line.startswith("## ") or line.startswith("### "):
            lvl = 1 if line.startswith("## ") else 2
            text = line.lstrip("#").strip()
            hp = doc.add_heading(text, level=lvl)
            for r in hp.runs:
                r.font.color.rgb = INK
            if lvl == 1:
                bookmark(hp, slug(text))
                for path, cap in list(img.items()):
                    pass
            i += 1
            continue
        if line.strip() == "---":
            i += 1
            continue
        if line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            emit_runs(p, line[2:])
            i += 1
            continue
        if line.strip():
            block = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith(
                    ("#", "|", "- ", "---")):
                i += 1
                block.append(lines[i])
            p = doc.add_paragraph()
            emit_runs(p, " ".join(x.strip() for x in block))
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        i += 1

    for path, cap in (images or {}).items():
        if Path(path).exists():
            doc.add_page_break()
            hp = doc.add_heading(cap, level=1)
            for r in hp.runs:
                r.font.color.rgb = INK
            doc.add_picture(path, width=Inches(6.5))
    doc.save(out)
    print(f"wrote {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("md", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--image", action="append", default=[])
    a = ap.parse_args(argv)
    images = {}
    for spec in a.image:
        path, _, cap = spec.partition("=")
        images[path] = cap or Path(path).stem
    build(a.md, a.out, images)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
