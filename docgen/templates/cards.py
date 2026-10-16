"""KYC cards (PAN, Aadhaar, passport, driving licence, Voter ID) and the cancelled cheque.

Labels follow DECISIONS D3: PAN is always Proof of Identity; Aadhaar, DL,
passport and Voter ID are Proof of Address when the page shows an address,
otherwise Proof of Identity. The mapping lives in config/subtypes.yaml.
Card text is English only (base-14 fonts); real cards also carry Hindi.
"""
from __future__ import annotations

import string
from datetime import timedelta

from common import identifiers as ids
from docgen import fake
from docgen.layout import A4, CHEQUE, EMBLEM, GREY, ID1, ID3, KV, P, PHOTO, QR, R, SIGN, TB, WHITE, BARS, Doc, L, Page, T
from docgen.templates import template
from docgen.templates.common import centered

W1 = ID1[0]
SAFFRON, GREEN, NAVY, RED = (1, 0.6, 0.2), (0.1, 0.55, 0.2), (0.1, 0.1, 0.45), (0.8, 0.1, 0.1)


MASKED_ON_CARDS = 0.3  # ASSUMED share of Aadhaar copies printed masked (UIDAI's masked download); D23


def _addr_lines(p, prefix: bool = True) -> list[str]:
    head = [f"{'S/O' if p.gender == 'MALE' else 'D/O'} {p.father},"] if prefix else []
    return head + [p.house + ",", p.street + ", " + p.locality + ",", f"{p.city}, {p.state} - {p.pin}"]


@template("pan_card")
def pan(rng, st, subtype):
    p = fake.person(rng)
    pg = Page(ID1, bg=rng.choice([(0.82, 0.9, 0.97), (0.86, 0.92, 0.98), (0.9, 0.93, 0.97)]))
    pg.add(T(8, 13, "INCOME TAX DEPARTMENT", size=6.3, bold=True, color=NAVY), EMBLEM(121, 13, 15),
           T(178, 13, "GOVT. OF INDIA", size=6.3, bold=True, color=NAVY))
    if st.variant >= 2 or rng.random() < 0.5:  # newer design: photo left, QR right
        pg.add(T(58, 32, "Permanent Account Number Card", size=6, bold=True), T(70, 44, p.pan, size=9, bold=True),
               PHOTO(8, 28, 44, 54), KV(58, 60, [("Name", p.name.upper()), ("Father's Name", p.father.upper()), ("Date of Birth", fake.fmt_date(p.dob, 1))],
                                        size=5.4, lw=52), QR(192, 92, 42, rng.random()), SIGN(10, 118, 60, rng.random()), T(10, 134, "Signature", size=5))
    else:  # older design: text left, photo bottom right
        pg.add(T(10, 40, p.name.upper(), size=7, bold=True), T(10, 52, p.father.upper(), size=7, bold=True), T(10, 64, fake.fmt_date(p.dob, 1), size=7, bold=True),
               T(10, 82, "Permanent Account Number", size=6), T(10, 96, p.pan, size=10, bold=True), SIGN(10, 122, 60, rng.random()),
               T(10, 138, "Signature", size=5), PHOTO(178, 60, 54, 68))
    return Doc("PAN Card", [pg], "helv")


@template("aadhaar_front", "aadhaar_back")
def aadhaar_card(rng, st, subtype):
    p = fake.person(rng)
    num = fake.aadhaar_shown(rng, p.aadhaar, MASKED_ON_CARDS)
    pg = Page(ID1, bg=(1, 1, 1))
    pg.add(R(0, 0, W1, 5, fill=SAFFRON, stroke=None), R(0, 8, W1, 4, fill=GREEN, stroke=None))
    if subtype == "aadhaar_front":
        pg.add(EMBLEM(18, 26, 18), T(38, 28, "GOVERNMENT OF INDIA", size=8, bold=True), PHOTO(10, 40, 50, 62),
               T(70, 54, p.name, size=7, bold=True))
        pg.add(T(70, 66, f"DOB: {fake.fmt_date(p.dob, 1)}" if rng.random() < 0.8 else f"Year of Birth: {p.dob.year}", size=6.5))
        pg.add(T(70, 78, p.gender.title() if rng.random() < 0.5 else p.gender, size=6.5),
               centered(num, 120, 11, bold=True, width=W1))
        if rng.random() < 0.4:
            pg.add(centered(f"VID : 9{rng.randint(10**14, 10**15 - 1)}", 131, 5.5, width=W1))
        pg.add(L(0, 139, W1, 139, color=RED, lw=1.2), centered("Mera Aadhaar, Meri Pehchaan", 149, 6, bold=True, color=RED, width=W1))
    else:
        pg.add(T(10, 24, "Unique Identification Authority of India", size=7.2, bold=True, color=NAVY), T(10, 40, "Address:", size=6.5, bold=True))
        for i, line in enumerate(_addr_lines(p)):
            pg.add(T(10, 50 + i * 9, line, size=5.8))
        pg.add(QR(176, 30, 58, rng.random()), L(0, 112, W1, 112, color=RED, lw=1),
               centered(num, 126, 10, bold=True, width=W1),
               T(10, 146, "1947", size=6.5, bold=True, color=RED), T(60, 146, "help@uidai.gov.in", size=5.5), T(150, 146, "www.uidai.gov.in", size=5.5))
    return Doc("Aadhaar", [pg], "helv")


@template("e_aadhaar_letter")
def e_aadhaar(rng, st, subtype):
    p = fake.person(rng)
    num = fake.aadhaar_shown(rng, p.aadhaar, MASKED_ON_CARDS)
    pg = Page(A4)
    pg.add(T(36, 50, "Unique Identification Authority of India", size=13, bold=True, color=NAVY), T(36, 66, "Government of India", size=9),
           EMBLEM(540, 50, 26), T(36, 100, f"Enrolment No.: {rng.randint(1000, 9999)}/{rng.randint(10000, 99999)}/{rng.randint(10000, 99999)}", size=8),
           T(36, 122, "To", size=8))
    for i, line in enumerate([p.name] + _addr_lines(p) + [f"Mobile: {p.mobile[:2]}XXXXXX{p.mobile[-2:]}"]):
        pg.add(T(36, 136 + i * 11, line, size=8.5))
    pg.add(T(36, 230, f"Aadhaar no. issued: {fake.fmt_date(fake.rand_date(rng, 2011, 2024), 1)}", size=8),
           centered("Your Aadhaar No. :", 290, 11, bold=True), centered(num, 316, 17, bold=True),
           centered("Mera Aadhaar, Meri Pehchaan", 344, 10, bold=True, color=RED), L(36, 400, 559, 400, color=GREY))
    pg.add(R(36, 420, 250, 158, stroke=GREY), R(309, 420, 250, 158, stroke=GREY),
           T(46, 438, "GOVERNMENT OF INDIA", size=7.5, bold=True), PHOTO(46, 446, 52, 64), T(108, 460, p.name, size=7, bold=True),
           T(108, 472, f"DOB: {fake.fmt_date(p.dob, 1)}", size=6.5), T(108, 484, p.gender, size=6.5), centered(num, 556, 11, bold=True, width=250, x0=36),
           T(319, 438, "Address:", size=7, bold=True))
    for i, line in enumerate(_addr_lines(p)):
        pg.add(T(319, 450 + i * 10, line, size=6.5))
    pg.add(QR(490, 500, 58, rng.random()), centered(num, 566, 10, bold=True, width=250, x0=309),
           P(36, 610, 523, 90, "Information: Aadhaar is a proof of identity, not of citizenship. Verify identity using Secure QR Code, Offline XML or "
                               "Online Authentication. This is an electronically generated letter.", size=8))
    return Doc("e-Aadhaar", [pg], "helv")


def _mrz(p, pno: str, expiry) -> tuple[str, str]:
    name = (p.last.upper() + "<<" + p.first.upper().replace(" ", "<"))
    l1 = ("P<IND" + "".join(c if c in string.ascii_uppercase + "<" else "<" for c in name) + "<" * 44)[:44]
    num = (pno + "<<<")[:9]
    dob, exp, personal = p.dob.strftime("%y%m%d"), expiry.strftime("%y%m%d"), "<" * 14
    c1, c2, c3, c4 = (ids.mrz_check_digit(x) for x in (num, dob, exp, personal))
    body = f"{num}{c1}IND{dob}{c2}{p.gender[0]}{exp}{c3}{personal}{c4}"
    comp = ids.mrz_check_digit(f"{num}{c1}{dob}{c2}{exp}{c3}{personal}{c4}")
    return l1, body + str(comp)


@template("passport_data_page", "passport_address_page")
def passport(rng, st, subtype):
    p = fake.person(rng)
    pno = ids.fake_passport_no(rng)
    issue = fake.rand_date(rng, 2016, 2025)
    expiry = issue + timedelta(days=3652)
    pg = Page(ID3, bg=(0.94, 0.91, 0.95))
    if subtype == "passport_data_page":
        pg.add(T(110, 16, "REPUBLIC OF INDIA", size=9, bold=True, color=(0.2, 0.1, 0.4)), EMBLEM(326, 18, 18))
        for x, label, val in ((110, "Type", "P"), (150, "Country Code", "IND"), (226, "Passport No.", pno)):
            pg.add(T(x, 32, label, size=5, color=GREY), T(x, 41, val, size=7.5, bold=True))
        pg.add(PHOTO(12, 28, 82, 102))
        fields = [("Surname", p.last.upper()), ("Given Name(s)", p.first.upper()), ("Nationality / Sex / Date of Birth", f"INDIAN    {p.gender[0]}    {fake.fmt_date(p.dob, 1)}"),
                  ("Place of Birth", f"{p.city.upper()}, {p.state.upper()}"), ("Place of Issue", rng.choice(["MUMBAI", "PUNE", "BENGALURU", "CHENNAI", "DELHI", "HYDERABAD"])),
                  ("Date of Issue / Date of Expiry", f"{fake.fmt_date(issue, 1)}    {fake.fmt_date(expiry, 1)}")]
        for i, (label, val) in enumerate(fields):
            pg.add(T(110, 56 + i * 20, label, size=5, color=GREY), T(110, 64 + i * 20, val, size=7, bold=True))
        l1, l2 = _mrz(p, pno, expiry)
        pg.add(SIGN(12, 150, 70, rng.random()), T(12, 210, l1, size=8.6, font="cour"), T(12, 226, l2, size=8.6, font="cour"))
    else:
        pg.add(T(240, 14, f"Passport No. {pno}", size=6.5, bold=True))
        fields = [("Name of Father / Legal Guardian", p.father.upper()), ("Name of Mother", p.mother.upper()), ("Name of Spouse", "")]
        for i, (label, val) in enumerate(fields):
            pg.add(T(14, 30 + i * 22, label, size=5.5, color=GREY), T(14, 39 + i * 22, val, size=7.5, bold=True))
        pg.add(T(14, 100, "Address", size=5.5, color=GREY))
        for i, line in enumerate(_addr_lines(p, prefix=False)):
            pg.add(T(14, 110 + i * 10, line.upper(), size=7, bold=True))
        pg.add(T(14, 160, "Old Passport No. with Date and Place of Issue", size=5.5, color=GREY), T(14, 170, "N/A", size=7),
               T(14, 188, "File No.", size=5.5, color=GREY), T(14, 197, f"{rng.choice(['BO', 'MU', 'PN', 'CH'])}{rng.randint(10**10, 10**11 - 1)}", size=7, bold=True),
               BARS(200, 200, 140, 26, rng.random()))
    return Doc("Passport", [pg], "helv")


@template("dl_front", "dl_back")
def driving_licence(rng, st, subtype):
    p = fake.person(rng)
    dl = f"{p.rto}{rng.randint(1, 50):02d} {rng.randint(2005, 2024)}{rng.randint(0, 9999999):07d}"
    issue = fake.rand_date(rng, 2010, 2025)
    pg = Page(ID1, bg=(0.95, 0.96, 0.93))
    pg.add(R(0, 0, W1, 18, fill=st.accent, stroke=None), T(8, 12, "INDIAN UNION DRIVING LICENCE", size=7, bold=True, color=WHITE))
    if subtype == "dl_front":
        pg.add(T(8, 28, f"Issued by Government of {p.state}", size=5.5),
               KV(8, 42, [("DL No.", dl), ("Issue Date", fake.fmt_date(issue, 1)), ("Validity (NT)", fake.fmt_date(issue + timedelta(days=7300), 1)),
                          ("Name", p.name.upper()), ("S/D/W of", p.father.upper()), ("Date of Birth", fake.fmt_date(p.dob, 1)),
                          ("Blood Group", rng.choice(["A+", "B+", "O+", "AB+", "O-"]))], size=5.6, lw=50),
               PHOTO(186, 24, 48, 58), SIGN(186, 100, 50, rng.random()), T(186, 112, "Signature", size=4.8))
    else:
        pg.add(T(8, 30, "Address:", size=6, bold=True))
        for i, line in enumerate(_addr_lines(p)):
            pg.add(T(8, 40 + i * 8.5, line, size=5.5))
        pg.add(TB(8, 80, [60, 70], [["Class of Vehicle", "Date of Issue"], ["MCWG", fake.fmt_date(issue, 1)], ["LMV", fake.fmt_date(issue, 1)]], size=5.2),
               T(8, 136, f"Issuing Authority: RTO, {p.city.upper()}", size=5.5), T(8, 146, f"Emergency Contact No.: {p.mobile}", size=5.2))
        if rng.random() < 0.5:
            pg.add(QR(176, 74, 56, rng.random()))
    return Doc("Driving Licence", [pg], "helv")


@template("voter_id_front", "voter_id_back")
def voter_id(rng, st, subtype):
    p = fake.person(rng)
    pg = Page(ID1, bg=(0.97, 0.97, 0.99))
    if subtype == "voter_id_front":
        epic = "".join(rng.choice(string.ascii_uppercase) for _ in range(3)) + f"{rng.randint(0, 9999999):07d}"
        pg.add(centered("ELECTION COMMISSION OF INDIA", 12, 7, bold=True, width=W1),
               centered(rng.choice(["IDENTITY CARD", "ELECTOR PHOTO IDENTITY CARD"]), 22, 6, bold=True, width=W1),
               centered(epic, 34, 8, bold=True, width=W1), PHOTO(10, 42, 50, 62),
               KV(70, 54, [("Elector's Name", p.name), ("Father's Name" if p.gender == "MALE" or rng.random() < 0.5 else "Husband's Name", p.father),
                           ("Sex", p.gender.title()), ("Date of Birth", fake.fmt_date(p.dob, 1))], size=5.5, lw=58))
    else:
        pg.add(T(8, 16, "Address:", size=6.5, bold=True))
        for i, line in enumerate(_addr_lines(p, prefix=False)):
            pg.add(T(8, 27 + i * 9, line, size=5.8))
        ac = rng.randint(1, 288)
        pg.add(T(8, 68, f"Assembly Constituency No. & Name: {ac} - {p.locality}", size=5.4), T(8, 78, f"Part No. & Name: {rng.randint(1, 350)} - {rng.choice(fake.BUILDINGS)}", size=5.4),
               SIGN(130, 110, 70, rng.random()), T(130, 124, "Electoral Registration Officer", size=5.2),
               T(8, 124, f"Date: {fake.fmt_date(fake.rand_date(rng, 2010, 2025), 1)}", size=5.4))
    return Doc("Voter ID", [pg], "helv")


@template("cancelled_cheque")
def cheque(rng, st, subtype):
    p = fake.person(rng)
    code, bank = fake.bank(rng)
    pg = Page(CHEQUE, bg=(0.93, 0.95, 0.98))
    pg.add(T(16, 24, bank.upper(), size=12, bold=True, color=st.accent), T(16, 36, f"{rng.choice(fake.LOCALITIES)} Branch, {p.city}", size=6.5),
           T(16, 46, f"IFSC: {ids.fake_ifsc(rng, code)}", size=6.5), T(430, 22, "Date", size=6.5))
    for i in range(8):
        pg.add(R(452 + i * 14, 12, 12, 14, stroke=GREY, lw=0.5))
    pg.add(T(16, 78, "Pay", size=8), L(40, 80, 440, 80, color=GREY), T(445, 78, "or Bearer", size=7),
           T(16, 104, "Rupees", size=8), L(54, 106, 400, 106, color=GREY), R(430, 92, 130, 22, stroke=GREY), T(434, 106, "Rs.", size=8),
           T(16, 140, f"A/c No. {rng.randint(10**10, 10**14)}", size=8, bold=True), T(16, 152, rng.choice(["SB", "CA"]) + " A/c", size=6.5),
           T(400, 190, p.name.upper(), size=7), T(400, 205, "Please sign above", size=6),
           T(60, 248, f"{rng.randint(100000, 999999)}   {rng.randint(10**8, 10**9 - 1)}   {rng.randint(100000, 999999)}   {rng.choice(['10', '11', '29', '31'])}", size=11, font="cour"),
           T(140, 170, "CANCELLED", size=44, bold=True, color=(0.75, 0.1, 0.1), rot=-12),
           L(120, 120, 470, 200, color=(0.75, 0.1, 0.1), lw=1.5), L(120, 135, 470, 215, color=(0.75, 0.1, 0.1), lw=1.5))
    return Doc("Cancelled cheque", [pg], "helv")
