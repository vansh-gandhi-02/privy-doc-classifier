"""Documents outside the 15 classes: decks, system exports, stray photos and
blank pages, emails without attachments, archives. Passbooks, cheques,
utility bills and letters live with their look-alikes in finance, cards and forms.

The email template is a deliberate trap: it talks about loan applications,
salary slips and bank statements without being any of them.
"""
from __future__ import annotations

from docgen import fake
from docgen.layout import A4, PHOTO, R, TB, Doc, Page, T, P
from docgen.templates import template
from docgen.templates.forms import letter

SLIDE = (720.0, 405.0)


@template("generic_deck")
def deck(rng, st, subtype):
    co = fake.company(rng)
    titles = [f"{co.name}: Quarterly Business Review", "Agenda", "Key Highlights", "Branch Performance", "Customer Acquisition", "Risks and Mitigations", "Next Steps"]
    bullets = ["Revenue grew in line with plan", "New branches opened in two cities", "Digital onboarding share increased", "Collections efficiency improved",
               "Attrition remains a concern", "Pilot for the new product starts next quarter", "Budget approval required for hiring"]
    pages = []
    for t in titles[: rng.randint(3, 7)]:
        pg = Page(SLIDE).add(T(40, 60, t, size=20, bold=True))
        for i, b in enumerate(rng.sample(bullets, rng.randint(2, 5))):
            pg.add(T(60, 110 + i * 26, b, size=13))
        pages.append(pg)
    return Doc(titles[0], pages, st.font)


@template("system_text")
def system_text(rng, st, subtype):
    if rng.random() < 0.5:
        lines = [f"2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d} "
                 f"{rng.choice(['INFO', 'WARN', 'DEBUG'])} batch_id={rng.randint(1000, 9999)} job={rng.choice(['sync', 'export', 'reconcile'])} status={rng.choice(['ok', 'retry', 'done'])}"
                 for _ in range(rng.randint(20, 60))]
        pg = Page(A4)
        for i, line in enumerate(lines):
            pg.add(T(36, 40 + i * 12, line, size=7, font="cour"))
        return Doc("system log", [pg], "cour")
    rows = [["Item Code", "Description", "Qty", "Rate", "Amount"]]
    for _ in range(rng.randint(10, 40)):
        q, r = rng.randint(1, 500), rng.uniform(10, 5000)
        rows.append([f"IT{rng.randint(1000, 9999)}", rng.choice(["Printer cartridge", "A4 paper ream", "Laptop charger", "Chair", "Cable", "Toner"]),
                     str(q), f"{r:.2f}", f"{q * r:.2f}"])
    return Doc("inventory", [Page(A4).add(TB(36, 40, [80, 200, 60, 80, 103], rows, size=7))], st.font)


@template("photo_or_blank")
def photo_or_blank(rng, st, subtype):
    pg = Page((600.0, 450.0))
    kind = rng.choice(["blank", "scene", "selfie"])
    if kind == "blank":
        pg.bg = (1, 1, 1)
    elif kind == "scene":
        pg.bg = (0.55, 0.7, 0.9)
        pg.add(R(0, 250, 600, 200, fill=(0.35, 0.5, 0.3), stroke=None), R(rng.randint(50, 400), 150, 120, 110, fill=(0.7, 0.6, 0.5), stroke=None))
    else:
        pg.bg = (0.8, 0.8, 0.82)
        pg.add(PHOTO(150, 40, 300, 380))
    return Doc("photo", [pg], "helv")


@template("email_no_attachment")
def email_body(rng, st, subtype):
    p = fake.person(rng)
    code, bank = fake.bank(rng)
    subject = rng.choice(["Re: Documents pending for your loan application", "Your credit card application status", "KYC update reminder",
                          "Fwd: statement request", "Salary slips for loan processing"])
    body = (f"Dear {p.first},\n\nWe have received your application no. {rng.randint(10**6, 10**7)}. The following documents are still pending: "
            "salary slips for the last three months, bank statement for the last six months and a copy of your PAN card. Please upload them "
            f"through the customer portal or reply to this email.\n\nRegards,\nLoan Processing Team\n{bank}")
    return Doc(subject, [Page(A4).add(P(36, 40, 523, 300, body, size=9))], "helv")


@template("archive_or_heic")
def archive(rng, st, subtype):
    return letter(rng, st, "misc_letter")
