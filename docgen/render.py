"""Turn a template's Doc into a file of the requested format.

PDF digital       drawn with PyMuPDF, real text layer
PDF scan          pages rasterised, degraded, wrapped back into a PDF with no text layer
JPG / PNG / TIFF  rasterised then degraded as a scan, phone photo or screenshot
                  (JPG/PNG keep page 1; TIFF keeps every page, like a scanner)
DOCX / XLSX / TXT / PPTX  the same blocks written in reading order
EML               an email; the attachment is passed in by build_sample (D12)
OTH               a ZIP holding the document as a PDF
"""
from __future__ import annotations

import io
import math
import random
import zipfile
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone

import pymupdf
from PIL import Image

from docgen import degrade
from docgen.layout import BLACK, FONTS, Doc

PHOTO_FILL = (0.82, 0.84, 0.86)


def _fn(b: dict, doc_font: str, bold: bool = False) -> str:
    return FONTS[b.get("font") or doc_font][1 if bold else 0]


def _fit(text: str, fontname: str, size: float, width: float) -> str:
    if pymupdf.get_text_length(text, fontname=fontname, fontsize=size) <= width:
        return text
    while text and pymupdf.get_text_length(text + "..", fontname=fontname, fontsize=size) > width:
        text = text[:-1]
    return text + ".."


def _draw(pg: pymupdf.Page, b: dict, df: str) -> None:
    k = b["k"]
    if k == "text":
        fn = _fn(b, df, b["bold"])
        if b["rot"]:
            pt = pymupdf.Point(b["x"], b["y"])
            pg.insert_text(pt, b["s"], fontname=fn, fontsize=b["size"], color=b["color"], morph=(pt, pymupdf.Matrix(b["rot"])))
        else:
            pg.insert_text((b["x"], b["y"]), b["s"], fontname=fn, fontsize=b["size"], color=b["color"])
    elif k == "para":
        rect, size = pymupdf.Rect(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]), b["size"]
        while size >= 4 and pg.insert_textbox(rect, b["s"], fontname=_fn(b, df, b["bold"]), fontsize=size,
                                              align=b["align"], color=b["color"]) < 0:
            size -= 0.5
    elif k == "kv":
        y = b["y"]
        for label, val in b["pairs"]:
            pg.insert_text((b["x"], y), label, fontname=_fn(b, df), fontsize=b["size"], color=b["color"])
            vfn = FONTS[b["vfont"]][0] if b["vfont"] else _fn(b, df, True)
            pg.insert_text((b["x"] + b["lw"], y), val, fontname=vfn, fontsize=b["size"], color=BLACK)
            y += b["lh"]
    elif k == "table":
        _table(pg, b, df)
    elif k == "rect":
        pg.draw_rect(pymupdf.Rect(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]), color=b["stroke"], fill=b["fill"], width=b["lw"])
    elif k == "line":
        pg.draw_line((b["x1"], b["y1"]), (b["x2"], b["y2"]), color=b["color"], width=b["lw"])
    elif k == "photo":
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        pg.draw_rect(pymupdf.Rect(x, y, x + w, y + h), color=(0.5, 0.5, 0.5), fill=PHOTO_FILL, width=0.5)
        pg.draw_oval(pymupdf.Rect(x + w * 0.12, y + h * 0.62, x + w * 0.88, y + h), color=None, fill=(0.35, 0.37, 0.45))
        pg.draw_oval(pymupdf.Rect(x + w * 0.32, y + h * 0.14, x + w * 0.68, y + h * 0.6), color=None, fill=(0.62, 0.52, 0.45))
    elif k == "qr":
        _qr(pg, b)
    elif k == "seal":
        c, r = pymupdf.Point(b["x"], b["y"]), b["r"]
        pg.draw_circle(c, r, color=b["color"], width=1.3)
        pg.draw_circle(c, r * 0.78, color=b["color"], width=0.6)
        pg.insert_textbox(pymupdf.Rect(c.x - r * 0.72, c.y - r * 0.42, c.x + r * 0.72, c.y + r * 0.6), b["s"],
                          fontname="hebo", fontsize=max(3.5, r / 4.2), align=1, color=b["color"])
    elif k == "sign":
        rng = random.Random(b["seed"])
        pts, x = [], b["x"]
        while x < b["x"] + b["w"]:
            pts.append((x, b["y"] + rng.uniform(-5, 5) * math.sin(x / rng.uniform(2, 6))))
            x += rng.uniform(1.5, 4)
        if len(pts) > 1:
            sh = pg.new_shape()
            sh.draw_polyline(pts)
            sh.finish(color=b["color"], width=0.9, closePath=False)
            sh.commit()
    elif k == "thumb":
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        for i in range(5):
            d = i * min(w, h) * 0.09
            pg.draw_oval(pymupdf.Rect(x + d, y + d, x + w - d, y + h - d), color=(0.3, 0.35, 0.6),
                         fill=(0.62, 0.66, 0.8) if i == 0 else None, width=0.5)
    elif k == "emblem":
        x, y, s, col = b["x"], b["y"], b["s"], b["color"]
        pg.draw_circle((x, y - s * 0.15), s * 0.28, color=col, width=0.8)
        for dx in (-0.22, 0, 0.22):
            pg.draw_rect(pymupdf.Rect(x + dx * s - s * 0.06, y + s * 0.1, x + dx * s + s * 0.06, y + s * 0.42), color=col, fill=col)
        pg.draw_line((x - s * 0.4, y + s * 0.45), (x + s * 0.4, y + s * 0.45), color=col, width=1)
    elif k == "check":
        x, y, s = b["x"], b["y"], b["s"]
        pg.draw_rect(pymupdf.Rect(x, y, x + s, y + s), color=BLACK, width=0.6)
        if b["checked"]:
            pg.draw_line((x + 1, y + 1), (x + s - 1, y + s - 1), width=0.9)
            pg.draw_line((x + s - 1, y + 1), (x + 1, y + s - 1), width=0.9)
    elif k == "bars":
        rng, x = random.Random(b["seed"]), b["x"]
        while x < b["x"] + b["w"]:
            bw = rng.choice([0.6, 1.0, 1.6])
            pg.draw_rect(pymupdf.Rect(x, b["y"], x + bw, b["y"] + b["h"]), color=None, fill=BLACK)
            x += bw + rng.choice([0.6, 1.0, 1.6])


def _table(pg: pymupdf.Page, b: dict, df: str) -> None:
    x0, y, rh, size, widths = b["x"], b["y"], b["rh"], b["size"], b["widths"]
    xs = [x0]
    for w in widths:
        xs.append(xs[-1] + w)
    top = y
    for i, row in enumerate(b["rows"]):
        head = b["header"] and i == 0
        fn = _fn(b, df, head)
        if head and b["ruled"]:
            pg.draw_rect(pymupdf.Rect(x0, y, xs[-1], y + rh), color=None, fill=(0.88, 0.88, 0.88))
        for j, cell in enumerate(row[: len(widths)]):
            text = _fit(cell, fn, size, widths[j] - 4)
            right = b["align"] and b["align"][j] == 2 and not head
            tx = xs[j] + widths[j] - 2 - pymupdf.get_text_length(text, fontname=fn, fontsize=size) if right else xs[j] + 2
            pg.insert_text((tx, y + rh * 0.68), text, fontname=fn, fontsize=size)
        if b["ruled"] or head:
            pg.draw_line((x0, y + (rh if head else 0)), (xs[-1], y + (rh if head else 0)), width=0.4)
        y += rh
    if b["ruled"]:
        pg.draw_line((x0, y), (xs[-1], y), width=0.4)
        for x in xs:
            pg.draw_line((x, top), (x, y), width=0.4)


def _qr(pg: pymupdf.Page, b: dict) -> None:
    rng, n = random.Random(b["seed"]), 25
    m = b["s"] / n
    on = [[rng.random() < 0.5 for _ in range(n)] for _ in range(n)]
    for (r0, c0) in ((0, 0), (0, n - 7), (n - 7, 0)):
        for r in range(7):
            for c in range(7):
                edge = r in (0, 6) or c in (0, 6)
                core = 2 <= r <= 4 and 2 <= c <= 4
                on[r0 + r][c0 + c] = edge or core
    sh = pg.new_shape()
    for r in range(n):
        for c in range(n):
            if on[r][c]:
                sh.draw_rect(pymupdf.Rect(b["x"] + c * m, b["y"] + r * m, b["x"] + (c + 1) * m, b["y"] + (r + 1) * m))
    sh.finish(color=None, fill=BLACK)
    sh.commit()


def to_pdf(doc: Doc) -> pymupdf.Document:
    pdf = pymupdf.open()
    for page in doc.pages:
        pg = pdf.new_page(width=page.size[0], height=page.size[1])
        if page.bg:
            pg.draw_rect(pg.rect, color=None, fill=page.bg)
        for b in page.blocks:
            _draw(pg, b, doc.font)
    return pdf


def page_images(pdf: pymupdf.Document, max_pages: int | None = None, long_side: int = 1500) -> list[Image.Image]:
    out = []
    for i, pg in enumerate(pdf):
        if max_pages and i >= max_pages:
            break
        dpi = int(min(300, max(90, long_side / (max(pg.rect.width, pg.rect.height) / 72))))
        pix = pg.get_pixmap(dpi=dpi)
        out.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return out


def _reading_order(blocks: list[dict]) -> list[dict]:
    def key(b):
        y = b.get("y", b.get("y1", 0))
        return (round(y / 6), b.get("x", b.get("x1", 0)))
    return sorted((b for b in blocks if b["k"] in ("text", "para", "kv", "table")), key=key)


def text_lines(doc: Doc) -> list[str]:
    """The document's text in reading order, one entry per line or row."""
    lines = []
    for page in doc.pages:
        for b in _reading_order(page.blocks):
            if b["k"] in ("text", "para"):
                lines.append(b["s"])
            elif b["k"] == "kv":
                lines.extend(f"{a}: {v}" if v else a for a, v in b["pairs"])
            else:
                lines.extend(", ".join(r) for r in b["rows"])
    return lines


def _write_docx(doc: Doc, path) -> None:
    import docx
    d = docx.Document()
    for i, page in enumerate(doc.pages):
        if i:
            d.add_page_break()
        for b in _reading_order(page.blocks):
            if b["k"] in ("text", "para"):
                d.add_paragraph().add_run(b["s"]).bold = b["bold"]
            elif b["k"] == "kv":
                t = d.add_table(rows=len(b["pairs"]), cols=2)
                for r, (a, v) in enumerate(b["pairs"]):
                    t.cell(r, 0).text, t.cell(r, 1).text = a, v
            else:
                cols = max(len(r) for r in b["rows"])
                t = d.add_table(rows=len(b["rows"]), cols=cols)
                t.style = "Table Grid"
                for r, row in enumerate(b["rows"]):
                    for c, cell in enumerate(row):
                        t.cell(r, c).text = cell
    d.save(path)


def _num(s: str):
    t = s.replace(",", "").replace("Rs.", "").strip()
    try:
        return float(t) if t and any(ch.isdigit() for ch in t) else s
    except ValueError:
        return s


def _write_xlsx(doc: Doc, path) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    ws, r = wb.active, 1
    ws.title = doc.title[:30] or "Sheet1"
    for page in doc.pages:
        for b in _reading_order(page.blocks):
            if b["k"] in ("text", "para"):
                ws.cell(r, 1, b["s"])
                r += 1
            elif b["k"] == "kv":
                for a, v in b["pairs"]:
                    ws.cell(r, 1, a), ws.cell(r, 2, _num(v))
                    r += 1
            else:
                for row in b["rows"]:
                    for c, cell in enumerate(row, start=1):
                        ws.cell(r, c, _num(cell))
                    r += 1
        r += 1
    wb.save(path)


def _write_pptx(doc: Doc, path) -> None:
    from pptx import Presentation
    prs = Presentation()
    for page in doc.pages:
        lines = [b["s"] for b in _reading_order(page.blocks) if b["k"] in ("text", "para")]
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = lines[0] if lines else doc.title
        body = slide.placeholders[1].text_frame
        body.text = "\n".join(lines[1:9])
    prs.save(path)


def _write_eml(doc: Doc, path, rng: random.Random, attachment: tuple | None) -> None:
    msg = EmailMessage()
    msg["From"] = f"customer{rng.randint(100, 999)}@{rng.choice(['gmail.com', 'yahoo.co.in', 'outlook.com'])}"
    msg["To"] = rng.choice(["documents@bank.example", "loans@bank.example", "kyc@bank.example"])
    msg["Subject"] = doc.title
    msg["Date"] = format_datetime(datetime(2026, rng.randint(1, 9), rng.randint(1, 28), rng.randint(8, 20), tzinfo=timezone.utc))
    msg.set_content("\n".join(text_lines(doc)))
    if attachment:
        name, data, maintype, subtype = attachment
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    with open(path, "wb") as f:
        f.write(bytes(msg))


def attachment_bytes(doc: Doc, rng: random.Random) -> tuple:
    """A class document as an email attachment: a digital PDF or a phone photo."""
    pdf = to_pdf(doc)
    if rng.random() < 0.65:
        return "document.pdf", pdf.tobytes(deflate=True), "application", "pdf"
    img = degrade.phone_photo(page_images(pdf, 1)[0], rng)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=rng.randint(55, 85))
    return "IMG_%04d.jpg" % rng.randint(1, 9999), buf.getvalue(), "image", "jpeg"


def pdf_document(doc: Doc, modality: str, rng: random.Random, pdf: pymupdf.Document | None = None) -> pymupdf.Document:
    """The document as a PDF: drawn directly when digital, otherwise each page
    rasterised, degraded and wrapped back into an image-only PDF."""
    pdf = pdf or to_pdf(doc)
    if modality == "digital":
        return pdf
    out = pymupdf.open()
    for page, img in zip(pdf, page_images(pdf)):
        buf = io.BytesIO()
        _degrade(img, modality, rng).convert("RGB").save(buf, "JPEG", quality=rng.randint(50, 85))
        out.new_page(width=page.rect.width, height=page.rect.height).insert_image(page.rect, stream=buf.getvalue())
    return out


def _degrade(img: Image.Image, modality: str, rng: random.Random) -> Image.Image:
    if modality == "photo":
        return degrade.phone_photo(img, rng)
    if modality == "screenshot":
        return degrade.screenshot(img, rng)
    return degrade.scan(img, rng)


def write(doc: Doc, fmt: str, modality: str, path, rng: random.Random, attachment: tuple | None = None) -> int:
    """Write `doc` to `path` as `fmt`. Returns the page count of the written file."""
    if fmt in ("DOCX", "XLSX", "TXT", "PPTX", "EML"):
        {"DOCX": _write_docx, "XLSX": _write_xlsx, "PPTX": _write_pptx}.get(fmt, lambda *_: None)(doc, path)
        if fmt == "TXT":
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(text_lines(doc)) + "\n")
        if fmt == "EML":
            _write_eml(doc, path, rng, attachment)
        return len(doc.pages)

    pdf = to_pdf(doc)
    if fmt == "OTH":
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("scan_%04d.pdf" % rng.randint(1, 9999), pdf.tobytes(deflate=True))
        return len(doc.pages)
    if fmt == "PDF":
        out = pdf_document(doc, modality, rng, pdf)
        out.save(path, deflate=True)
        return len(out)
    if fmt == "TIFF":
        imgs = [_degrade(img, modality, rng).convert("L") for img in page_images(pdf)]
        imgs[0].save(path, "TIFF", save_all=True, append_images=imgs[1:], compression="tiff_lzw")
        return len(imgs)
    img = _degrade(page_images(pdf, 1)[0], modality, rng)
    if fmt == "JPG":
        img.convert("RGB").save(path, "JPEG", quality=rng.randint(55, 90))
    else:
        img.save(path, "PNG", optimize=True)
    return 1
