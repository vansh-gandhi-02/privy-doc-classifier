"""Agreements, deeds and constitutional documents.

Deliberate overlaps, matching DECISIONS D6:
- rent agreements describe a property and carry a schedule of premises, and
  some have a registration page with photos and thumb impressions, just like
  a sale deed, but they are Legal Contracts
- every agreement opens with an e-stamp or stamp-paper page; the stamp's
  "Description of Document" (Article 5(h) Agreement vs 25(b) Conveyance) is a
  real discriminator that a careful reader can use
"""
from __future__ import annotations

from docgen import fake
from docgen.layout import A4, EMBLEM, GREY, KV, P, PHOTO, QR, R, SEAL, SIGN, TB, THUMB, Doc, Page, T
from docgen.templates import template
from docgen.templates.common import Flow, centered

GENERIC = [
    ("Governing Law", "This {doc} shall be governed by and construed in accordance with the laws of India, and the courts at {city} shall have exclusive jurisdiction."),
    ("Arbitration", "Any dispute arising out of or in connection with this {doc} shall be referred to a sole arbitrator under the Arbitration and Conciliation Act, 1996, and the seat of arbitration shall be {city}."),
    ("Notices", "All notices under this {doc} shall be in writing and delivered at the addresses of the parties first written above, or such other address as a party may notify."),
    ("Severability", "If any provision of this {doc} is held invalid or unenforceable, the remaining provisions shall continue in full force and effect."),
    ("Entire Agreement", "This {doc} constitutes the entire understanding between the parties and supersedes all prior discussions and arrangements."),
]
SPECIFIC = {
    "LOAN AGREEMENT": [("The Loan", "The Lender agrees to lend and the Borrower agrees to borrow the sum of Rs. {amt} on the terms of this Agreement."),
                       ("Interest", "The Borrower shall pay interest at the rate of {rate}% per annum, computed on the daily outstanding balance and payable monthly."),
                       ("Repayment", "The loan shall be repaid in {emis} equated monthly instalments by way of NACH mandate in favour of the Lender."),
                       ("Events of Default", "Non-payment of any instalment on its due date, or any misrepresentation by the Borrower, shall constitute an event of default.")],
    "DEED OF GUARANTEE": [("Guarantee", "In consideration of the Bank granting credit facilities to the Borrower, the Guarantor irrevocably guarantees the due repayment of Rs. {amt}."),
                          ("Continuing Guarantee", "This guarantee shall be a continuing guarantee and shall remain in force until all dues of the Borrower are paid in full."),
                          ("Demand", "The Guarantor shall pay the amount demanded by the Bank within seven days of a written demand, without demur or protest.")],
    "SERVICE AGREEMENT": [("Scope of Services", "The Service Provider shall provide the services described in Annexure A to the reasonable satisfaction of the Company."),
                          ("Fees", "The Company shall pay the Service Provider a monthly fee of Rs. {amt}, plus applicable GST, within thirty days of invoice."),
                          ("Term and Termination", "This Agreement shall remain in force for {emis} months and may be terminated by either party on thirty days' written notice.")],
    "NON-DISCLOSURE AGREEMENT": [("Confidential Information", "Confidential Information means all non-public business, technical and financial information disclosed by the Disclosing Party."),
                                 ("Obligations", "The Receiving Party shall use the Confidential Information only for the Purpose and shall not disclose it to any third party."),
                                 ("Term", "The obligations under this Agreement shall survive for a period of three years from the date of disclosure.")],
    "DIRECT SELLING AGENT AGREEMENT": [("Appointment", "The Bank appoints the DSA on a non-exclusive basis to source applications for retail loan products."),
                                       ("Commission", "The DSA shall be paid commission at the rates set out in Schedule I on loans disbursed through its sourcing."),
                                       ("Code of Conduct", "The DSA shall comply with the Fair Practices Code and the Code of Conduct for DSAs issued by the Bank.")],
}


def _stamp(rng, st, pg: Page, p, article: str, prop: str, consideration: float, duty: int, first: str, second: str) -> float:
    """First-page stamp: an e-stamp certificate or old-style stamp paper. Returns the y below it."""
    rto = p.rto
    if st.variant in (0, 2):
        pg.add(R(36, 36, 523, 330, fill=(0.98, 0.93, 0.95), stroke=GREY), centered("INDIA NON JUDICIAL", 62, 14, st, bold=True),
               centered(f"Government of {p.state}", 76, 9, st), centered("e-Stamp", 92, 11, st, bold=True),
               KV(56, 116, [("Certificate No.", f"IN-{rto}{rng.randint(10**13, 10**14 - 1)}{rng.choice('ABCDEFGHJKLMNPQRSTUVWX')}"),
                            ("Certificate Issued Date", fake.fmt_date(fake.rand_date(rng, 2020, 2026), 2)),
                            ("Account Reference", f"SHCIL (FI)/ {rto.lower()}shcil{rng.randint(1, 99):02d}/ {p.city.upper()}/ {rto}-{p.city[:3].upper()}"),
                            ("Unique Doc. Reference", f"SUBIN-{rto}{rto.lower()}shcil{rng.randint(10**12, 10**13)}"), ("Purchased by", first),
                            ("Description of Document", article), ("Property Description", prop[:70]), ("Consideration Price (Rs.)", fake.inr(consideration, 0)),
                            ("First Party", first), ("Second Party", second), ("Stamp Duty Paid By", first),
                            ("Stamp Duty Amount(Rs.)", f"{fake.inr(duty, 0)} ({fake.words(duty)} only)")], size=7.5, lw=150),
               QR(480, 110, 60, rng.random()),
               P(56, 318, 480, 40, "Statutory Alert: 1. The authenticity of this Stamp certificate should be verified at www.shcilestamp.com or using the "
                                   "e-Stamp Mobile App of Stock Holding. Any discrepancy in the details on this Certificate and as available on the website "
                                   "renders it invalid. 2. The onus of checking the legitimacy is on the users of the certificate.", size=6))
        return 380
    pg.add(R(0, 0, 595, 170, fill=(0.96, 0.88, 0.78), stroke=None), EMBLEM(80, 70, 40), centered("INDIA NON JUDICIAL", 60, 18, st, bold=True),
           centered(f"Rs. {fake.inr(duty, 0)}", 96, 20, st, bold=True), centered(f"{fake.words(duty).upper()} RUPEES", 118, 9, st),
           centered(p.state.upper(), 140, 9, st), T(470, 160, f"No. {rng.randint(100000, 999999)}", size=8))
    return 190


def _ids(rng, person, show: bool) -> str:
    """Registered deeds quote the parties' PAN, and often Aadhaar (Rule 114B; from memory, D23)."""
    if not show:
        return ""
    out = f", holding PAN {person.pan}"
    if rng.random() < 0.6:
        out += f" and Aadhaar No. {fake.aadhaar_shown(rng, person.aadhaar, 0.5)}"
    return out


def _parties(rng, role1: str, role2: str, bank_party: bool, show_ids: bool = False):
    a = fake.person(rng)
    if bank_party:
        code, bank = fake.bank(rng)
        b_name, b_desc = bank, (f"{bank}, a banking company within the meaning of the Banking Regulation Act, 1949, having its branch office at "
                                f"{rng.choice(fake.LOCALITIES)}, {a.city}")
    else:
        b = fake.person(rng)
        b_name, b_desc = b.name, f"{b.name}, aged about {2026 - b.dob.year} years{_ids(rng, b, show_ids)}, residing at {b.address}"
    a_desc = f"{a.name}, aged about {2026 - a.dob.year} years{_ids(rng, a, show_ids)}, residing at {a.address}"
    return a, a_desc, b_name, b_desc


def _signatures(rng, f: Flow, role1: str, role2: str, registration: bool, p) -> None:
    f.para("IN WITNESS WHEREOF the parties hereto have set and subscribed their respective hands on the day and year first hereinabove written.", 9)
    y = f.need(150)
    for i, role in enumerate((role1, role2)):
        x = f.x + i * 250
        f.page.add(T(x, y + 14, f"SIGNED AND DELIVERED by the within named {role.upper()}", size=7.5), SIGN(x, y + 46, 100, rng.random()))
    f.page.add(T(f.x, y + 90, "WITNESSES:", size=8, bold=True), T(f.x, y + 106, "1.", size=8), SIGN(f.x + 14, y + 104, 80, rng.random()),
               T(f.x + 250, y + 106, "2.", size=8), SIGN(f.x + 264, y + 104, 80, rng.random()))
    if registration:
        pg = Page(A4)
        pg.add(centered(f"Office of the Sub-Registrar, {p.city} {rng.randint(1, 12)}", 50, 11, f.st, bold=True),
               centered(f"Document No. {p.city[:3].upper()}-{rng.randint(1, 12)}-{rng.randint(1000, 99999)}-{rng.randint(2015, 2026)}", 66, 9, f.st),
               P(54, 80, 487, 40, "Presented at the office of the Sub-Registrar together with the fees as shown below. The executants named "
                                  "below admitted execution of the document before me.", size=8))
        for i, role in enumerate((role1, role2)):
            y = 140 + i * 150
            pg.add(T(54, y, role.upper(), size=9, bold=True), PHOTO(54, y + 8, 80, 100), THUMB(160, y + 20, 60, 76),
                   T(160, y + 112, "Left thumb impression", size=7), SIGN(260, y + 70, 100, rng.random()), T(260, y + 86, "Signature", size=7))
        pg.add(TB(54, 460, [240, 150], [["Particulars", "Amount (Rs.)"], ["Registration fee", fake.inr(rng.choice([100, 1000, 30000]), 0)],
                                         ["Document handling charges", fake.inr(rng.choice([300, 800, 1400]), 0)]], size=8),
               SEAL(450, 540, 40, "SUB-REGISTRAR"), SIGN(400, 600, 100, rng.random()), T(400, 616, "Sub-Registrar", size=8))
        f.pages.append(pg)


@template("legal_agreement", "rent_agreement", "sale_deed", "mortgage_deed")
def agreement(rng, st, subtype):
    p = fake.person(rng)
    city = p.city
    prop_text = None
    if subtype == "legal_agreement":
        title = rng.choice(list(SPECIFIC))
        role1, role2 = {"LOAN AGREEMENT": ("Borrower", "Lender"), "DEED OF GUARANTEE": ("Guarantor", "Bank"), "SERVICE AGREEMENT": ("Service Provider", "Company"),
                        "NON-DISCLOSURE AGREEMENT": ("Disclosing Party", "Receiving Party"), "DIRECT SELLING AGENT AGREEMENT": ("DSA", "Bank")}[title]
        article, prop, consideration = ("Article 12 Bond" if "GUARANTEE" in title else "Article 5(h) Agreement"), "Not Applicable", rng.choice([0, 0, 500000, 2500000])
        duty, bank_party, registration = rng.choice([100, 500]), role2 in ("Lender", "Bank"), False
        clauses = SPECIFIC[title] + rng.sample(GENERIC, 3)
        doc_word = "Agreement" if "AGREEMENT" in title else "Deed"
    else:
        prop_text = (f"Flat No. {rng.randint(101, 1404)}, {rng.randint(1, 14)} floor, {rng.choice(fake.BUILDINGS)} Co-operative Housing Society, "
                     f"Survey No. {rng.randint(10, 400)}/{rng.randint(1, 9)}, CTS No. {rng.randint(100, 9999)}, {p.locality}, {city}, {p.state} - {p.pin}, "
                     f"admeasuring {rng.randint(350, 2200)} sq. ft. carpet area")
        prop = prop_text
        if subtype == "rent_agreement":
            title, role1, role2 = rng.choice([("LEAVE AND LICENSE AGREEMENT", "Licensor", "Licensee"), ("RENT AGREEMENT", "Landlord", "Tenant")])
            rent = rng.randint(8, 120) * 1000
            article, consideration, duty = "Article 36A Leave and License", rent * 11, max(100, round(rent * 11 * 0.0025))
            bank_party, registration, doc_word = False, rng.random() < 0.5, "Agreement"
            clauses = [("Licence Period", f"The licence is granted for a period of eleven months commencing from {fake.fmt_date(fake.rand_date(rng, 2023, 2026), 2)}."),
                       ("Compensation", f"The {role2} shall pay a monthly compensation of Rs. {fake.inr(rent, 0)} on or before the fifth day of every month."),
                       ("Deposit", f"The {role2} has paid an interest-free refundable security deposit of Rs. {fake.inr(rent * rng.choice([3, 6, 10]), 0)}."),
                       ("Use", f"The {role2} shall use the premises for residential purposes only and shall not sublet or part with possession."),
                       ("Charges", f"Electricity and maintenance charges for the licence period shall be borne by the {role2}.")] + rng.sample(GENERIC, 2)
        elif subtype == "sale_deed":
            title, role1, role2 = rng.choice([("SALE DEED", "Vendor", "Purchaser"), ("DEED OF CONVEYANCE", "Vendor", "Purchaser")])
            price = rng.randint(20, 400) * 100000
            article, consideration, duty = "Article 25(b) Conveyance", price, round(price * rng.choice([0.05, 0.06]))
            bank_party, registration, doc_word = False, True, "Deed"
            clauses = [("Sale", f"In consideration of Rs. {fake.inr(price, 0)} paid by the {role2}, the {role1} hereby sells, conveys and transfers the said property to the {role2}."),
                       ("Title", f"The {role1} declares that the said property is free from all encumbrances, charges, liens and attachments, and that the {role1} has a clear and marketable title."),
                       ("Possession", f"The {role1} has handed over vacant and peaceful possession of the said property to the {role2} on execution of this Deed."),
                       ("Indemnity", f"The {role1} shall indemnify the {role2} against any claim made by any person claiming through the {role1}.")]
        else:
            title, role1, role2 = rng.choice([("MEMORANDUM OF DEPOSIT OF TITLE DEEDS", "Mortgagor", "Mortgagee"), ("DEED OF SIMPLE MORTGAGE", "Mortgagor", "Mortgagee")])
            loan = rng.randint(10, 300) * 100000
            article, consideration, duty = "Article 6(1) Agreement relating to Deposit of Title Deeds", loan, round(loan * 0.003)
            bank_party, registration, doc_word = True, rng.random() < 0.5, "Deed"
            clauses = [("Deposit", f"The {role1} has deposited the original title deeds listed in the Second Schedule with the {role2} with intent to create security for a loan of Rs. {fake.inr(loan, 0)}."),
                       ("Security", f"The said property shall remain charged to the {role2} until the entire loan with interest is repaid."),
                       ("Covenants", f"The {role1} shall not sell, lease or otherwise encumber the said property without the prior written consent of the {role2}.")]
    a, a_desc, b_name, b_desc = _parties(rng, role1, role2, bank_party, show_ids=registration or rng.random() < 0.3)
    pg = Page(A4)
    y = _stamp(rng, st, pg, p, article, prop, consideration, duty, a.name, b_name)
    f = Flow(st, first=pg, y=y + 10)
    f.heading(title, 13)
    d = fake.rand_date(rng, 2020, 2026)
    f.para(f"THIS {title} is made and executed at {city} on this {d.day} day of {fake.MONTHS[d.month - 1]}, {d.year} BY AND BETWEEN:", 9)
    f.para(f"{a_desc} (hereinafter referred to as the \"{role1}\", which expression shall unless repugnant to the context or meaning thereof mean "
           f"and include his/her heirs, executors, administrators and assigns) of the ONE PART;", 9)
    f.para("AND", 9, bold=True, align=1)
    f.para(f"{b_desc} (hereinafter referred to as the \"{role2}\", which expression shall include its successors and assigns) of the OTHER PART.", 9)
    if prop_text:
        f.para(f"WHEREAS the {role1} is the absolute owner and in peaceful possession of the property more particularly described in the Schedule "
               "hereunder written (hereinafter referred to as the \"said property\");", 9)
    f.para(f"NOW THIS {doc_word.upper()} WITNESSETH AND IT IS HEREBY AGREED BY AND BETWEEN THE PARTIES AS FOLLOWS:", 9, bold=True)
    amt, rate, emis = fake.inr(consideration or rng.randint(5, 50) * 100000, 0), rng.choice([9.5, 10.75, 12, 13.5]), rng.choice([12, 24, 36, 60])
    for i, (head, text) in enumerate(clauses, start=1):
        f.para(f"{i}. {head}. " + text.format(doc=doc_word, city=city, amt=amt, rate=rate, emis=emis), 9)
    if prop_text:
        f.heading("THE SCHEDULE ABOVE REFERRED TO" if subtype != "rent_agreement" else "SCHEDULE OF THE PREMISES", 10)
        f.para(f"All that piece and parcel of {prop_text}, bounded as follows: On or towards the North by {rng.choice(fake.STREETS)}; South by "
               f"{rng.choice(fake.BUILDINGS)}; East by open plot; West by {rng.choice(fake.STREETS)}.", 9)
    _signatures(rng, f, role1, role2, registration, p)
    return Doc(title.title(), f.pages, st.font)


@template("moa_aoa")
def moa_aoa(rng, st, subtype):
    co = fake.company(rng)
    f = Flow(st, y=60)
    f.heading("THE COMPANIES ACT, 2013", 10)
    f.heading("COMPANY LIMITED BY SHARES", 10)
    moa = rng.random() < 0.6
    if moa:
        f.heading(f"MEMORANDUM OF ASSOCIATION OF {co.name.upper()}", 12)
        f.para(f"I. The name of the Company is {co.name.upper()}.", 9.5)
        f.para(f"II. The Registered Office of the Company will be situated in the State of {co.state}.", 9.5)
        f.para("III. (a) The objects to be pursued by the Company on its incorporation are: to carry on the business of manufacturing, trading, "
               f"importing, exporting and dealing in {rng.choice(fake.CO_NOUN).lower()} and all related products and services, and to undertake "
               "all activities incidental or conducive to the attainment of the main objects.", 9.5)
        f.para("(b) Matters which are necessary for furtherance of the objects specified in clause III(a) are: to borrow or raise money, to open "
               "accounts with banks, to acquire property, and to enter into contracts and arrangements.", 9.5)
        f.para("IV. The liability of the member(s) is limited, and this liability is limited to the amount unpaid, if any, on the shares held by them.", 9.5)
        cap = rng.choice([1, 5, 10, 25, 100]) * 100000
        f.para(f"V. The Authorised Share Capital of the Company is Rs. {fake.inr(cap, 0)} divided into {fake.inr(cap // 10, 0)} Equity Shares of Rs. 10 each.", 9.5)
        f.para("We, the several persons whose names and addresses are subscribed, are desirous of being formed into a company in pursuance of this "
               "Memorandum of Association, and we respectively agree to take the number of shares in the capital of the Company set against our names.", 9.5)
        rows = [["Name, address and occupation of subscriber", "Number of shares", "Signature"]]
        for _ in range(rng.randint(2, 3)):
            s = fake.person(rng)
            rows.append([f"{s.name}, {s.city}, Business", str(rng.choice([5000, 10000, 25000])), ""])
        y = f.need(len(rows) * 16 + 10)
        f.page.add(TB(f.x, y, [300, 100, 87], rows, size=8))
    else:
        f.heading(f"ARTICLES OF ASSOCIATION OF {co.name.upper()}", 12)
        for head, text in [("Interpretation", "In these regulations, the Act means the Companies Act, 2013, and the seal means the common seal of the Company."),
                           ("Share capital and variation of rights", "Subject to the provisions of the Act, the shares in the capital of the Company shall be under the control of the Directors."),
                           ("Lien", "The Company shall have a first and paramount lien on every share for all monies called or payable at a fixed time in respect of that share."),
                           ("Transfer of shares", "The instrument of transfer of any share in the Company shall be executed by or on behalf of both the transferor and transferee."),
                           ("Board of Directors", "The number of Directors shall not be less than two and not more than fifteen. The first Directors of the Company shall be named in the Memorandum."),
                           ("Borrowing powers", "The Board may, from time to time, raise or borrow any sums of money for and on behalf of the Company from banks and financial institutions."),
                           ("The Seal", "The Board shall provide for the safe custody of the seal, and the seal shall not be affixed except by the authority of a resolution of the Board.")]:
            f.heading(head, 10, center=False)
            f.para(text, 9.5)
    return Doc("Memorandum of Association" if moa else "Articles of Association", f.pages, st.font)
