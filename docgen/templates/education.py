"""Class 10 and Class 12 marksheets, CBSE and several state boards.

The hard pair by design: within a board, the Class 10 and Class 12 sheets
share a layout, so only the exam name tells them apart. Several board names
contain "Secondary" for both (e.g. "Board of Secondary Education, Rajasthan"
issues both the Secondary and the Senior Secondary sheets), so matching the
word "Secondary" alone is a trap.
"""
from __future__ import annotations

from docgen import fake
from docgen.layout import A4, EMBLEM, GREY, KV, QR, R, SIGN, TB, Doc, Page, T
from docgen.templates import template
from docgen.templates.common import centered

CBSE = ("CENTRAL BOARD OF SECONDARY EDUCATION", "SECONDARY SCHOOL EXAMINATION", "SENIOR SCHOOL CERTIFICATE EXAMINATION", "MARKS STATEMENT CUM CERTIFICATE")
STATE = [
    ("MAHARASHTRA STATE BOARD OF SECONDARY AND HIGHER SECONDARY EDUCATION, PUNE", "SECONDARY SCHOOL CERTIFICATE (SSC) EXAMINATION",
     "HIGHER SECONDARY CERTIFICATE (HSC) EXAMINATION", "STATEMENT OF MARKS"),
    ("KARNATAKA SCHOOL EXAMINATION AND ASSESSMENT BOARD", "S.S.L.C. EXAMINATION", None, "MARKS CARD"),
    ("DEPARTMENT OF PRE-UNIVERSITY EDUCATION, KARNATAKA", None, "II PUC EXAMINATION", "MARKS CARD"),
    ("BOARD OF SECONDARY EDUCATION, RAJASTHAN, AJMER", "SECONDARY EXAMINATION", "SENIOR SECONDARY EXAMINATION", "MARKS SHEET"),
    ("COUNCIL FOR THE INDIAN SCHOOL CERTIFICATE EXAMINATIONS, NEW DELHI", "INDIAN CERTIFICATE OF SECONDARY EDUCATION (ICSE) EXAMINATION",
     "INDIAN SCHOOL CERTIFICATE (ISC) EXAMINATION", "STATEMENT OF MARKS"),
    ("BOARD OF INTERMEDIATE EDUCATION, TELANGANA", None, "INTERMEDIATE PUBLIC EXAMINATION - SECOND YEAR", "MEMORANDUM OF MARKS"),
    ("BOARD OF SECONDARY EDUCATION, TELANGANA STATE", "SECONDARY SCHOOL CERTIFICATE EXAMINATION", None, "MEMORANDUM OF SUBJECT WISE GRADES"),
    ("GOVERNMENT OF TAMIL NADU, DEPARTMENT OF GOVERNMENT EXAMINATIONS", "SECONDARY SCHOOL LEAVING CERTIFICATE EXAMINATION",
     "HIGHER SECONDARY EXAMINATION", "MARK CERTIFICATE"),
]
SUBJECTS_10 = [["ENGLISH"], ["HINDI", "MARATHI", "KANNADA", "TAMIL", "SANSKRIT"], ["MATHEMATICS"], ["SCIENCE", "SCIENCE AND TECHNOLOGY"],
               ["SOCIAL SCIENCE", "SOCIAL SCIENCES"], ["INFORMATION TECHNOLOGY", "COMPUTER APPLICATIONS"]]
STREAMS_12 = [["ENGLISH CORE", "PHYSICS", "CHEMISTRY", "MATHEMATICS", "COMPUTER SCIENCE"],
              ["ENGLISH CORE", "PHYSICS", "CHEMISTRY", "BIOLOGY", "PHYSICAL EDUCATION"],
              ["ENGLISH", "ACCOUNTANCY", "BUSINESS STUDIES", "ECONOMICS", "MATHEMATICS"],
              ["ENGLISH", "HISTORY", "POLITICAL SCIENCE", "GEOGRAPHY", "ECONOMICS"]]
PRACTICAL = {"PHYSICS", "CHEMISTRY", "BIOLOGY", "COMPUTER SCIENCE", "PHYSICAL EDUCATION", "GEOGRAPHY", "INFORMATION TECHNOLOGY", "SCIENCE"}


def _grade(m: int) -> str:
    for cut, g in ((91, "A1"), (81, "A2"), (71, "B1"), (61, "B2"), (51, "C1"), (41, "C2"), (33, "D")):
        if m >= cut:
            return g
    return "E"


@template("marksheet_10_cbse", "marksheet_10_state", "marksheet_12_cbse", "marksheet_12_state")
def marksheet(rng, st, subtype):
    p = fake.person(rng)
    twelve = "_12_" in subtype
    if "cbse" in subtype:
        board = CBSE
    else:
        board = rng.choice([b for b in STATE if b[2 if twelve else 1]])
    name, exam10, exam12, doc_title = board
    exam = exam12 if twelve else exam10
    year = rng.randint(2008 + (2 if twelve else 0), 2025)
    subjects = rng.choice(STREAMS_12) if twelve else [rng.choice(s) for s in SUBJECTS_10[: rng.choice([5, 6])]]
    rows = [["Sub Code", "Subject", "Theory", "IA / Pr.", "Total", "Total (in words)", "Grade"]]
    total = 0
    for s in subjects:
        prac = s in PRACTICAL
        th = rng.randint(28, 70 if prac else 80)
        ia = rng.randint(14, 30 if prac else 20)
        m = th + ia
        total += m
        rows.append([f"{rng.randint(1, 399):03d}", s, f"{th:03d}", f"{ia:03d}", f"{m:03d}", fake.words(m).upper(), _grade(m)])
    pg = Page(A4, bg=rng.choice([(0.98, 0.96, 0.9), (0.94, 0.97, 0.94), (0.95, 0.95, 0.99)]))
    pg.add(R(20, 20, 555, 802, stroke=st.accent, lw=2), R(26, 26, 543, 790, stroke=st.accent, lw=0.6))
    if st.logo_right:
        pg.add(EMBLEM(520, 70, 34))
    else:
        pg.add(EMBLEM(297, 64, 34))
    y = 112
    for i, part in enumerate(_wrap(name, 52)):
        pg.add(centered(part, y + i * 14, 11.5, st, bold=True, color=st.accent))
    y += 14 * len(_wrap(name, 52)) + 8
    pg.add(centered(f"{exam}, {year}" if rng.random() < 0.7 else f"{exam} {fake.MONTHS[rng.choice([2, 3, 4])].upper()} {year}", y, 10.5, st, bold=True),
           centered(doc_title, y + 18, 10, st, bold=True))
    y += 40
    pg.add(KV(50, y, [("Roll No.", str(rng.randint(10**6, 10**8))), ("Candidate's Name", p.name.upper()), ("Mother's Name", p.mother.upper()),
                      ("Father's / Guardian's Name", p.father.upper()), ("Date of Birth", fake.fmt_date(p.dob, 1)),
                      ("School", f"{rng.choice(fake.BUILDINGS)} {rng.choice(['High School', 'Vidyalaya', 'Public School', 'Junior College'])}, {p.city}")],
                  size=8.5, lw=150))
    y += 6 * 13.2 + 14
    pg.add(TB(40, y, [48, 150, 46, 46, 42, 140, 43], rows, size=7.5))
    y += len(rows) * 7.5 * 1.75 + 18
    pct = total / len(subjects)
    pg.add(T(50, y, f"Grand Total: {total} / {len(subjects) * 100}", size=9, bold=True), T(250, y, f"Percentage: {pct:.2f}%", size=9, bold=True),
           T(420, y, "RESULT: PASS", size=9, bold=True))
    pg.add(T(50, 740, f"Date: {fake.fmt_date(fake.rand_date(rng, year, year), 0)}", size=8.5), SIGN(400, 735, 110, rng.random()),
           T(400, 752, rng.choice(["Controller of Examinations", "Divisional Secretary", "Secretary"]), size=8.5))
    if "cbse" in subtype or rng.random() < 0.4:
        pg.add(QR(50, 640, 70, rng.random()))
    if "cbse" in subtype and rng.random() < 0.5:
        pg.add(T(50, 790, "This is a digitally signed document issued through DigiLocker.", size=7, color=GREY))
    return Doc(doc_title.title(), [pg], st.font)


def _wrap(s: str, width: int) -> list[str]:
    out, line = [], ""
    for w in s.split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + [line]
