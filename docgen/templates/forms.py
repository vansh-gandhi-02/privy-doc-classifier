"""Forms, certificates, letters and reports: loan and card applications,
certificate of incorporation, board resolution, title search and valuation
reports, utility bills and letters to the bank.

Deliberate overlaps:
- loan and card applications share every section except one, and some
  carry no form title at all
- a board resolution talks about loans and bank accounts
- utility bills and change-of-address letters show a full address (PoA look-alikes)
"""
from __future__ import annotations

from docgen import fake
from docgen.layout import A4, EMBLEM, GREY, KV, PHOTO, R, SEAL, SIGN, TB, Doc, L, Page, T
from docgen.templates import template
from docgen.templates.common import Flow, centered, checks, header, section

MASKED_ON_FORMS = 0.5  # ASSUMED; forms carry full and masked Aadhaar numbers alike (D23)
LOAN_TYPES = ["Home Loan", "Personal Loan", "Vehicle Loan", "Loan Against Property", "Education Loan", "Business Loan"]
DECLARATION = ("I/We declare that all the particulars and information given in this application form are true, correct and complete and that "
               "they shall form the basis of any facility the Bank may decide to grant to me/us. I/We authorise the Bank to make references and "
               "enquiries relevant to this application and to share information with Credit Information Companies (CICs).")


@template("loan_application_form", "cc_application_form")
def application(rng, st, subtype):
    p, emp = fake.person(rng), fake.company(rng)
    code, bank = fake.bank(rng)
    loan = subtype == "loan_application_form"
    lt = rng.choice(LOAN_TYPES)
    if loan:
        title = rng.choices([f"Application Form for {lt}", f"{lt} Application Form", "Loan Application Form", "APPLICATION FORM"], [3, 3, 2, 1])[0]
    else:
        title = rng.choices(["Credit Card Application Form", "Application for Credit Card", "Card Application Form", "APPLICATION FORM"], [4, 2, 2, 1])[0]
    pg = Page(A4)
    y = header(pg, st, bank, [f"{rng.choice(fake.LOCALITIES)} Branch"])
    pg.add(centered(title, y + 14, 12, st, bold=True), T(36, y + 34, f"Application No.: {rng.randint(10**6, 10**7)}", size=8, font="cour"))
    if rng.random() < 0.75:
        pg.add(PHOTO(470, y - 4, 76, 92))
    else:
        pg.add(R(470, y - 4, 76, 92, stroke=GREY), T(476, y + 40, "Affix recent", size=6), T(476, y + 50, "photograph", size=6))
    y += 96
    y = section(pg, st, y, "A. PERSONAL DETAILS")
    pg.add(KV(40, y, [("Name of Applicant", p.name.upper()), ("Father's / Spouse's Name", p.father.upper()), ("Date of Birth", fake.fmt_date(p.dob, 1)),
                      ("PAN", p.pan), ("Aadhaar No.", fake.aadhaar_shown(rng, p.aadhaar, MASKED_ON_FORMS)), ("Mobile No.", p.mobile), ("Email ID", p.email),
                      ("Residential Address", p.address_lines[0]), ("", p.address_lines[1]), ("", p.address_lines[2])], size=8, lw=150, vfont="cour"))
    y += 10 * 12.4 + 4
    pg.add(T(40, y, "Gender", size=8), *checks(190, y, ["Male", "Female", "Other"], p.gender.title()))
    pg.add(T(40, y + 16, "Residence Type", size=8), *checks(190, y + 16, ["Owned", "Rented", "Parental", "Company"], rng.choice(["Owned", "Rented", "Parental"])))
    y += 36
    y = section(pg, st, y, "B. EMPLOYMENT / INCOME DETAILS")
    pg.add(T(40, y, "Occupation", size=8), *checks(190, y, ["Salaried", "Self-employed", "Professional"], rng.choice(["Salaried", "Self-employed"])))
    pg.add(KV(40, y + 16, [("Name of Employer / Business", emp.name), ("Designation", rng.choice(["Manager", "Engineer", "Proprietor", "Consultant"])),
                           ("Office Address", emp.address_lines[2]), ("Gross Monthly Income (Rs.)", fake.inr(rng.randint(25000, 400000), 0)),
                           ("Total Work Experience (years)", str(rng.randint(1, 30)))], size=8, lw=150, vfont="cour"))
    p2 = Page(A4)
    y = 60
    if loan:
        y = section(p2, st, y, "C. LOAN DETAILS")
        p2.add(KV(40, y, [("Loan Type", lt), ("Loan Amount Required (Rs.)", fake.inr(rng.choice([2, 5, 10, 25, 50, 80]) * 100000, 0)),
                          ("Tenure (months)", str(rng.choice([12, 24, 36, 60, 120, 180, 240]))), ("Purpose of Loan", rng.choice(["Purchase of flat", "Higher studies", "Business expansion", "Purchase of car", "Medical"])),
                          ("Co-applicant Name", fake.person(rng).name.upper())], size=8, lw=150, vfont="cour"))
        y += 5 * 12.4 + 4
        p2.add(T(40, y, "Rate Type", size=8), *checks(190, y, ["Fixed", "Floating"], rng.choice(["Fixed", "Floating"])),
               T(40, y + 16, "Repayment Mode", size=8), *checks(190, y + 16, ["NACH", "ECS", "Standing Instruction"], "NACH"))
        y = section(p2, st, y + 34, "D. EXISTING LOANS")
        rows = [["Lender", "Loan Type", "EMI (Rs.)", "Outstanding (Rs.)"]] + [[rng.choice(["HDFC Bank", "SBI", "Bajaj Finance", "ICICI Bank"]), rng.choice(LOAN_TYPES),
                                                                             fake.inr(rng.randint(2000, 60000), 0), fake.inr(rng.randint(20000, 3000000), 0)] for _ in range(rng.randint(0, 3))]
    else:
        y = section(p2, st, y, "C. CARD DETAILS")
        cards = rng.sample(["Platinum", "Rewards", "Millennia", "Regalia", "Signature", "Travel One"], 4)
        p2.add(T(40, y, "Card Variant", size=8), *checks(190, y, cards, rng.choice(cards)))
        name = (p.first + " " + p.last).upper()[:20]
        p2.add(T(40, y + 18, "Name to appear on Card", size=8))
        for i, ch in enumerate(name.ljust(20)):
            p2.add(R(190 + i * 13, y + 9, 12, 13, stroke=GREY, lw=0.5), T(193 + i * 13, y + 19, ch, size=8, font="cour"))
        p2.add(T(40, y + 38, "Add-on Card Required", size=8), *checks(190, y + 38, ["Yes", "No"], rng.choice(["Yes", "No"])),
               T(40, y + 54, "Statement Delivery", size=8), *checks(190, y + 54, ["Email", "Physical"], "Email"),
               T(40, y + 70, "Communication Address", size=8), *checks(190, y + 70, ["Residence", "Office"], "Residence"))
        y = section(p2, st, y + 88, "D. EXISTING CREDIT CARDS")
        rows = [["Issuer", "Card No. (last 4 digits)", "Credit Limit (Rs.)", "Card Holder Since"]] + [[rng.choice(["SBI Card", "HDFC Bank", "Axis Bank", "AMEX"]), str(rng.randint(1000, 9999)),
                                                                                                      fake.inr(rng.choice([50000, 100000, 200000]), 0), str(rng.randint(2010, 2025))] for _ in range(rng.randint(0, 3))]
    p2.add(TB(40, y, [130, 130, 130, 125], rows, size=8))
    y += len(rows) * 14 + 20
    y = section(p2, st, y, "DECLARATION")
    flow = Flow(st, first=p2, y=y, x=40, w=515)
    flow.para(DECLARATION, 8)
    y = flow.y + 30
    p2.add(SIGN(40, y, 110, rng.random()), T(40, y + 16, "Signature of Applicant", size=8), T(260, y + 16, f"Date: {fake.fmt_date(fake.rand_date(rng, 2024, 2026), 1)}", size=8),
           T(400, y + 16, f"Place: {p.city}", size=8), R(40, y + 40, 515, 60, stroke=GREY), T(46, y + 54, "FOR BANK USE ONLY", size=8, bold=True),
           KV(46, y + 70, [("Sourced by (DSA / Branch code)", f"DSA{rng.randint(1000, 9999)}"), ("Application received on", fake.fmt_date(fake.rand_date(rng, 2024, 2026), 0))], size=7.5, lw=170, vfont="cour"))
    return Doc(title, [pg, p2], st.font)


@template("incorporation_certificate")
def incorporation(rng, st, subtype):
    co = fake.company(rng)
    d = co.incorporated
    pg = Page(A4)
    pg.add(R(20, 20, 555, 802, stroke=st.accent, lw=2), R(26, 26, 543, 790, stroke=st.accent, lw=0.6), EMBLEM(297, 70, 32),
           centered("GOVERNMENT OF INDIA", 110, 10, st, bold=True), centered("MINISTRY OF CORPORATE AFFAIRS", 124, 10, st, bold=True),
           centered(f"Registrar of Companies, {rng.choice(['Central Registration Centre', co.state])}", 140, 9, st),
           centered("Certificate of Incorporation", 180, 16, st, bold=True))
    f = Flow(st, first=pg, y=200, x=60, w=475)
    f.para("[Pursuant to sub-section (2) of section 7 and sub-section (1) of section 8 of the Companies Act, 2013 (18 of 2013) and rule 18 of "
           "the Companies (Incorporation) Rules, 2014]", 8, align=1)
    f.gap(10)
    f.para(f"I hereby certify that {co.name.upper()} is incorporated on this {d.day} day of {fake.MONTHS[d.month - 1]} {d.year} under the Companies "
           "Act, 2013 (18 of 2013) and that the company is limited by shares.", 10)
    f.para(f"The Corporate Identity Number of the company is {co.cin}.", 10)
    f.para(f"The Permanent Account Number (PAN) of the company is {co.pan}* and the Tax Deduction and Collection Account Number (TAN) "
           f"of the company is {co.pan[:4]}{fake.person(rng).last[0].upper()}{co.pan[5:]}*.", 10)
    f.para(f"Given under my hand at Manesar this {d.day} day of {fake.MONTHS[d.month - 1]} {d.year}.", 10)
    y = f.y + 20
    pg.add(R(330, y, 205, 60, stroke=GREY), T(338, y + 14, "Digital Signature Certificate", size=7.5, bold=True),
           T(338, y + 28, fake.person(rng).name.upper(), size=7.5), T(338, y + 42, "Assistant Registrar of Companies", size=7.5),
           T(60, y + 100, "Mailing Address as per record available in Registrar of Companies office:", size=8, bold=True),
           T(60, y + 114, co.name.upper(), size=8))
    for i, line in enumerate(co.address_lines):
        pg.add(T(60, y + 126 + i * 11, line, size=8))
    pg.add(T(60, 780, "*as issued by the Income Tax Department", size=7, color=GREY))
    return Doc("Certificate of Incorporation", [pg], st.font)


@template("board_resolution")
def board_resolution(rng, st, subtype):
    co = fake.company(rng)
    code, bank = fake.bank(rng)
    d = fake.rand_date(rng, 2020, 2026)
    dirs = [fake.person(rng) for _ in range(2)]
    pg = Page(A4)
    y = header(pg, st, co.name, [f"CIN: {co.cin}", co.address])
    f = Flow(st, first=pg, y=y + 16)
    opener = rng.choice(["CERTIFIED TRUE COPY OF THE RESOLUTION PASSED AT THE MEETING OF THE BOARD OF DIRECTORS OF",
                         "EXTRACT OF THE MINUTES OF THE MEETING OF THE BOARD OF DIRECTORS OF"])
    f.para(f"{opener} {co.name.upper()} HELD ON {fake.fmt_date(d, 2).upper()} AT {rng.randint(10, 17)}:00 HRS AT THE REGISTERED OFFICE OF THE COMPANY", 9.5, bold=True, align=1)
    topic = rng.choice(["account", "loan", "signatory"])
    amt = fake.inr(rng.choice([25, 50, 100, 250, 500]) * 100000, 0)
    first = {"account": f"RESOLVED THAT a current account be opened in the name of the Company with {bank}, {rng.choice(fake.LOCALITIES)} Branch, and that the "
                        "Bank be and is hereby authorised to honour cheques, bills of exchange and other instruments drawn, accepted or made on behalf of the Company.",
             "loan": f"RESOLVED THAT the consent of the Board be and is hereby accorded to avail a term loan / cash credit facility of Rs. {amt} from {bank} "
                     "on such terms and conditions as may be stipulated by the Bank, and to create security over the assets of the Company in favour of the Bank.",
             "signatory": f"RESOLVED THAT the authorised signatories for the operation of the Company's accounts with {bank} be changed with effect from "
                          f"{fake.fmt_date(d, 2)}, and that the specimen signatures of the new signatories be furnished to the Bank."}[topic]
    f.para(first, 9)
    f.para(f"RESOLVED FURTHER THAT {'Mr.' if dirs[0].gender == 'MALE' else 'Ms.'} {dirs[0].name}, Director (DIN: 0{rng.randint(1000000, 9999999)}), be and is hereby "
           "authorised to sign, execute and submit all such documents, agreements and writings as may be required, and to do all acts, deeds and "
           "things necessary to give effect to this resolution.", 9)
    f.para("RESOLVED FURTHER THAT a certified true copy of this resolution be furnished to the Bank and to such other parties as may be required.", 9)
    y = f.need(130)
    f.page.add(T(f.x, y + 16, f"For {co.name}", size=9, bold=True), SIGN(f.x, y + 50, 100, rng.random()),
               T(f.x, y + 68, dirs[1].name, size=8.5), T(f.x, y + 80, f"Director  DIN: 0{rng.randint(1000000, 9999999)}", size=8.5),
               SEAL(f.x + 300, y + 50, 34, co.name.upper()))
    if rng.random() < 0.6:
        f.page.add(R(f.x + 380, y + 90, 110, 22, stroke=(0.2, 0.2, 0.6)), T(f.x + 386, y + 105, "CERTIFIED TRUE COPY", size=8, bold=True, color=(0.2, 0.2, 0.6)))
    return Doc("Board Resolution", f.pages, st.font)


def _property(rng, p) -> str:
    return (f"Flat No. {rng.randint(101, 1404)}, {rng.randint(1, 14)} floor, {rng.choice(fake.BUILDINGS)} Co-operative Housing Society, "
            f"Survey No. {rng.randint(10, 400)}/{rng.randint(1, 9)}, CTS No. {rng.randint(100, 9999)}, {p.locality}, {p.city}, {p.state} - {p.pin}, "
            f"admeasuring {rng.randint(350, 2200)} sq. ft. carpet area")


@template("title_search_report")
def title_report(rng, st, subtype):
    adv, p = fake.person(rng), fake.person(rng)
    code, bank = fake.bank(rng)
    pg = Page(A4)
    y = header(pg, st, f"ADV. {adv.name.upper()}", ["B.Com., LL.B., Advocate, High Court", adv.address])
    f = Flow(st, first=pg, y=y + 10)
    f.para(f"Date: {fake.fmt_date(fake.rand_date(rng, 2022, 2026), 2)}", 9, align=0)
    f.para(f"To,\nThe Branch Manager,\n{bank},\n{rng.choice(fake.LOCALITIES)} Branch, {p.city}", 9, align=0)
    prop = _property(rng, p)
    f.para(f"Sub: {rng.choice(['Title Search Report', 'Legal Scrutiny Report', 'Report on Title'])} in respect of {prop}, owned by {p.name}.", 9, bold=True, align=0)
    f.para("Sir / Madam,", 9, align=0)
    f.para(f"As per your instructions, I have taken search in the office of the Sub-Registrar of Assurances at {p.city} for the last "
           f"{rng.choice([13, 30])} years, and have perused the original title documents produced before me by the borrower.", 9)
    rows = [["Sr. No.", "Description of Document", "Date", "Parties"]]
    for i in range(rng.randint(3, 6)):
        rows.append([str(i + 1), rng.choice(["Agreement for Sale", "Sale Deed", "Share Certificate", "Allotment Letter", "Occupancy Certificate", "Index II extract"]),
                     fake.fmt_date(fake.rand_date(rng, 1995, 2024), 0), f"{fake.person(rng).last} / {p.last}"])
    y = f.need(len(rows) * 14 + 10)
    f.page.add(TB(f.x, y, [50, 200, 80, 157], rows, size=8))
    f.para("Encumbrance: no encumbrance, charge or lis pendens was found registered against the said property during the period of search.", 9)
    f.para(f"OPINION: On perusal of the documents and the search, I am of the opinion that the title of {p.name} to the said property is clear and "
           "marketable and free from all encumbrances, and that the property can be accepted as security by way of equitable mortgage.", 9, bold=True)
    y = f.need(60)
    f.page.add(SIGN(f.x, y + 30, 100, rng.random()), T(f.x, y + 46, f"ADV. {adv.name.upper()}", size=8.5))
    return Doc("Title Search Report", f.pages, st.font)


@template("valuation_report")
def valuation(rng, st, subtype):
    val, p = fake.person(rng), fake.person(rng)
    code, bank = fake.bank(rng)
    area, rate = rng.randint(400, 2200), rng.randint(4000, 32000)
    fmv = area * rate
    pg = Page(A4)
    y = header(pg, st, f"{val.name}, B.E. (Civil)", [f"Government Approved Valuer, Reg. No. IBBI/RV/05/{rng.randint(2017, 2024)}/{rng.randint(10000, 99999)}", val.address])
    pg.add(centered(rng.choice(["VALUATION REPORT", "REPORT OF VALUATION OF IMMOVABLE PROPERTY"]), y + 14, 12, st, bold=True),
           T(36, y + 34, f"To, The Branch Manager, {bank}, {p.city}", size=8.5))
    rows = [["Sr.", "Particulars", "Details"], ["1", "Purpose of valuation", "For creation of mortgage in favour of the Bank"],
            ["2", "Date of inspection", fake.fmt_date(fake.rand_date(rng, 2023, 2026), 0)], ["3", "Name of the owner(s)", p.name],
            ["4", "Address of the property", f"{p.house}, {p.street}, {p.locality}"], ["", "", f"{p.city}, {p.state} - {p.pin}"],
            ["5", "Type of property", rng.choice(["Residential flat", "Commercial office", "Independent house", "Shop"])],
            ["6", "Carpet area (sq. ft.)", str(area)], ["7", "Age of the building (years)", str(rng.randint(0, 35))],
            ["8", "Rate adopted (Rs. per sq. ft.)", fake.inr(rate, 0)], ["9", "Fair Market Value (Rs.)", fake.inr(fmv, 0)],
            ["10", "Realisable Value (Rs.)", fake.inr(fmv * 0.9, 0)], ["11", "Distress Value (Rs.)", fake.inr(fmv * 0.8, 0)],
            ["12", "Government guideline value (Rs.)", fake.inr(fmv * rng.uniform(0.6, 0.9), 0)]]
    pg.add(TB(36, y + 48, [30, 200, 293], rows, size=8))
    y += 48 + len(rows) * 14 + 20
    for i in range(2):
        pg.add(R(36 + i * 262, y, 250, 150, fill=(0.8, 0.82, 0.8), stroke=GREY), L(36 + i * 262, y, 286 + i * 262, y + 150, color=GREY),
               T(40 + i * 262, y + 162, "Photograph of the property", size=7, color=GREY))
    y += 190
    pg.add(T(36, y, "I hereby declare that I have inspected the property and that the information furnished above is true and correct to the", size=8),
           T(36, y + 11, "best of my knowledge and belief, and that I have no direct or indirect interest in the property valued.", size=8),
           SIGN(36, y + 50, 100, rng.random()), T(36, y + 66, "Registered Valuer", size=8), SEAL(440, y + 50, 32, "GOVT. APPROVED VALUER"))
    return Doc("Valuation Report", [pg], st.font)


@template("utility_bill")
def utility_bill(rng, st, subtype):
    p = fake.person(rng)
    provider = rng.choice(["Maharashtra State Electricity Distribution Co. Ltd.", "Tata Power", "Adani Electricity Mumbai Limited",
                           "Bangalore Electricity Supply Company Limited", "Torrent Power Limited"])
    units = rng.randint(80, 900)
    amount = units * rng.uniform(6, 11) + rng.uniform(100, 400)
    pg = Page(A4)
    y = header(pg, st, provider, ["Bill of Supply for Electricity"])
    pg.add(centered(rng.choice(["ELECTRICITY BILL", "BILL OF SUPPLY", "Electricity Bill cum Receipt"]), y + 14, 12, st, bold=True),
           KV(36, y + 36, [("Consumer No.", str(rng.randint(10**11, 10**12 - 1))), ("Name", p.name.upper()), ("Address", p.address_lines[0]),
                           ("", p.address_lines[1]), ("", p.address_lines[2]), ("Tariff Category", rng.choice(["LT-I Residential", "LT-II Commercial"]))], size=8.5, lw=100),
           KV(330, y + 36, [("Bill Date", fake.fmt_date(fake.rand_date(rng, 2024, 2026), 0)), ("Due Date", fake.fmt_date(fake.rand_date(rng, 2024, 2026), 0)),
                            ("Units Consumed", str(units)), ("Total Amount Payable", "Rs. " + fake.inr(amount))], size=8.5, lw=120))
    rows = [["Charges", "Amount (Rs.)"], ["Energy Charges", fake.inr(amount * 0.7)], ["Fixed Charges", fake.inr(amount * 0.1)],
            ["Electricity Duty", fake.inr(amount * 0.15)], ["Wheeling Charges", fake.inr(amount * 0.05)], ["Total", fake.inr(amount)]]
    hist = [["Month", "Units"]] + [[fake.MONTHS[(i + 3) % 12][:3], str(rng.randint(60, 900))] for i in range(6)]
    pg.add(TB(36, y + 130, [180, 100], rows, size=8, align=[0, 2]), TB(360, y + 130, [80, 80], hist, size=8),
           T(36, y + 260, "Pay online through the website or mobile app. Ignore if already paid.", size=7.5, color=GREY))
    return Doc("Electricity Bill", [pg], st.font)


@template("misc_letter")
def letter(rng, st, subtype):
    p = fake.person(rng)
    code, bank = fake.bank(rng)
    topic = rng.choice(["change of address in my savings account", "issue of a new cheque book", "closure of my fixed deposit",
                        "a No Objection Certificate for my vehicle loan", "updating my registered mobile number"])
    f = Flow(st, y=70)
    f.para(f"Date: {fake.fmt_date(fake.rand_date(rng, 2023, 2026), 2)}", 9.5, align=0)
    f.para(f"To,\nThe Branch Manager,\n{bank},\n{rng.choice(fake.LOCALITIES)} Branch, {p.city}", 9.5, align=0)
    f.para(f"Subject: Request for {topic}", 9.5, bold=True, align=0)
    f.para("Dear Sir / Madam,", 9.5, align=0)
    body = f"I, {p.name}, hold savings account number {rng.randint(10**10, 10**14)} with your branch. I request you to kindly arrange for {topic}."
    if "address" in topic:
        body += f" My new address is {p.address}."
    f.para(body + " I have enclosed the required documents for your reference. Kindly do the needful at the earliest.", 9.5)
    f.para("Thanking you,\nYours faithfully,", 9.5, align=0)
    y = f.need(50)
    f.page.add(SIGN(f.x, y + 24, 90, rng.random()), T(f.x, y + 40, p.name, size=9))
    return Doc(f"Request for {topic}", f.pages, st.font)
