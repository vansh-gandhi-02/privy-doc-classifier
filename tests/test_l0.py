import io
from email.message import EmailMessage

import pymupdf
from PIL import Image

from pipeline.l0_open.metadata import open_file, prior_for

LINES = ["Statement of Account", "Customer ID 12345678", "Opening Balance 1,000.00", "Closing Balance 2,000.00"]


def _digital_pdf() -> bytes:
    d = pymupdf.open()
    p = d.new_page()
    for i, s in enumerate(LINES):
        p.insert_text((60, 100 + 20 * i), s, fontsize=12)
    return d.tobytes()


def _scan_with_hidden_text() -> bytes:
    src = pymupdf.open(stream=_digital_pdf(), filetype="pdf")
    png = src[0].get_pixmap(dpi=72).tobytes("png")
    d = pymupdf.open()
    p = d.new_page()
    p.insert_image(p.rect, stream=png)
    for i, s in enumerate(LINES):  # an OCR layer nobody can see
        p.insert_text((60, 100 + 20 * i), s, fontsize=12, render_mode=3)
    return d.tobytes()


def test_digital_pdf_is_text_route():
    r = open_file("a.pdf", _digital_pdf(), "c1", {})
    assert r.true_type == "PDF" and r.route == "text" and "Statement of Account" in r.text


def test_hidden_text_is_not_trusted():
    r = open_file("b.pdf", _scan_with_hidden_text(), "c2", {})
    assert r.route == "image" and r.text == ""


def test_extension_is_ignored():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "PNG")
    r = open_file("looks_like.pdf", buf.getvalue(), "c3", {})
    assert r.true_type == "PNG" and r.fmt == "PNG"


def test_email_attachment_becomes_the_document():
    msg = EmailMessage()
    msg["Subject"] = "Please find attached"
    msg.set_content("Regards")
    msg.add_attachment(_digital_pdf(), maintype="application", subtype="pdf", filename="x.pdf")
    r = open_file("m.eml", bytes(msg), "c4", {})
    assert r.true_type == "EML" and r.data[:4] == b"%PDF" and "Statement of Account" in r.text


def test_exact_duplicate_points_to_first_copy():
    seen = {}
    open_file("first.pdf", _digital_pdf(), "same", seen)
    r = open_file("second.pdf", _digital_pdf(), "same", seen)
    assert r.duplicate_of == "first.pdf"


def test_prior_never_zero_and_sums_to_one():
    p = prior_for("XLSX")
    assert abs(sum(p.values()) - 1) < 1e-9 and min(p.values()) > 0
    assert p["bank_statement"] > p["proof_of_identity"]
