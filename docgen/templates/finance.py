"""Statements, passbooks, salary slips, ITR, GST and audited financials.

Deliberate overlaps, so the classes are not trivially separable:
- passbooks share a statement's header words (customer ID, branch, balance)
- card statements sometimes carry "Customer ID" too
- salary slips carry a bank account number and "system generated" footers
- ITR and GST documents both show PAN, address and money tables
"""
from __future__ import annotations

import random
from datetime import timedelta

from common import identifiers as ids
from docgen import fake
from docgen.layout import A4, BARS, EMBLEM, GREY, KV, P, PASSBOOK, PHOTO, QR, R, SEAL, SIGN, TB, Doc, L, Page, T
from docgen.templates import template
from docgen.templates.common import Flow, centered, header

NARR = ["UPI/{n}/{who}/Payment", "NEFT CR-{ifsc}-{co}", "ATM WDL {city}", "SALARY CREDIT {co}", "IMPS/P2A/{n}/{who}",
        "POS {merchant}", "ACH D- {lender} EMI", "INT.PD", "CHQ DEP {n6}", "BIL/BPAY/{biller}", "RTGS CR {co}", "TO TRF {who}"]
WHO = ["RAHUL", "PRIYA", "AMIT", "SNEHA", "VIKRAM", "ANJALI", "KIRAN", "MOHAN", "DEEPA", "SURESH", "FATIMA", "ARJUN"]
MERCHANTS = ["AMAZON PAY", "SWIGGY", "DMART", "RELIANCE FRESH", "IRCTC", "ZOMATO", "INDIAN OIL", "FLIPKART", "BIGBASKET"]
LENDERS = ["BAJAJ FIN", "HDFC LTD", "TATA CAPITAL", "LIC HFL"]
BILLERS = ["MSEDCL", "AIRTEL", "JIO", "BESCOM", "MGL", "TATA POWER"]
CARD_PRODUCTS = ["Regalia", "Millennia", "Platinum Rewards", "SimplySAVE", "Coral", "Ace", "Select", "Elite"]


def _txns(rng: random.Random, n: int, d, bal: float):
    rows = []
    for _ in range(n):
        d += timedelta(days=rng.randint(0, 3))
        credit = rng.random() < 0.33
        amt = round(rng.uniform(150, 60000) if credit else rng.uniform(40, 18000), 2)
        if not credit and amt > bal:
            credit = True
        bal = round(bal + amt if credit else bal - amt, 2)
        narr = rng.choice(NARR).format(
            n=rng.randint(10**11, 10**12 - 1), n6=rng.randint(100000, 999999), who=rng.choice(WHO),
            ifsc=rng.choice(list(ids.BANK_CODES)) + "0" + str(rng.randint(100000, 999999)), co=rng.choice(fake.CO_PREFIX).upper(),
            city=rng.choice(fake.LOCALITIES).upper(), merchant=rng.choice(MERCHANTS), lender=rng.choice(LENDERS),
            biller=rng.choice(BILLERS))
        rows.append((d, narr, amt, credit, bal, str(rng.randint(10**7, 10**10))))
    return rows, bal, d


def _stmt_table(st, rows, v):
    f = lambda d: fake.fmt_date(d, v)
    if v == 0:
        head, w = ["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"], [50, 150, 78, 50, 62, 62, 71]
        body = [[f(d), n, ref, f(d), "" if c else fake.inr(a), fake.inr(a) if c else "", fake.inr(b)] for d, n, a, c, b, ref in rows]
    elif v == 1:
        head, w = ["Txn Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"], [55, 190, 90, 62, 62, 64]
        body = [[f(d), n, ref[:8], "" if c else fake.inr(a), fake.inr(a) if c else "", fake.inr(b)] for d, n, a, c, b, ref in rows]
    elif v == 2:
        head, w = ["Date", "Particulars", "Debit", "Credit", "Balance"], [60, 250, 70, 70, 73]
        body = [[f(d), n, "" if c else fake.inr(a), fake.inr(a) if c else "", fake.inr(b)] for d, n, a, c, b, ref in rows]
    else:
        head, w = ["Post Date", "Value Date", "Transaction Details", "Withdrawals (Dr)", "Deposits (Cr)", "Running Balance"], [55, 55, 185, 75, 75, 78]
        body = [[f(d), f(d), n, "" if c else fake.inr(a), fake.inr(a) if c else "", fake.inr(b)] for d, n, a, c, b, ref in rows]
    return head, w, body


@template("bank_estatement", "bank_statement_scan", "bank_statement_export")
def bank_statement(rng, st, subtype):
    p = fake.person(rng)
    code, bank = fake.bank(rng)
    ifsc = ids.fake_ifsc(rng, code)
    branch = f"{rng.choice(fake.LOCALITIES)} Branch"
    v = st.variant
    d0 = fake.rand_date(rng, 2024, 2026)
    n_pages = rng.randint(2, 4)
    open_bal = round(rng.uniform(2000, 400000), 2)
    rows, close, d_end = _txns(rng, 20 + 30 * (n_pages - 1), d0, open_bal)
    title = rng.choices(["Statement of Account", "Account Statement", "STATEMENT OF ACCOUNT", "Detailed Statement", None], [3, 3, 2, 1, 1])[0]
    cust, acct = str(rng.randint(10**7, 10**9)), str(rng.randint(10**10, 10**14))
    left = [("Customer Name", p.name.upper()), ("Address", p.address_lines[0]), ("", p.address_lines[1]),
            ("", p.address_lines[2]), ("Customer ID", cust), ("Account No", acct)]
    right = [("Account Type", rng.choice(["SAVINGS", "SAVINGS - REGULAR", "CURRENT ACCOUNT"])), ("Branch", branch), ("IFSC", ifsc),
             ("Currency", "INR"), ("Period", f"{fake.fmt_date(d0, v)} to {fake.fmt_date(d_end, v)}")]
    head, widths, body = _stmt_table(st, rows, v)
    debits = sum(r[2] for r in rows if not r[3])
    credits = sum(r[2] for r in rows if r[3])
    summary = [["Opening Balance", "Total Debits", "Total Credits", "Closing Balance"],
               [fake.inr(open_bal), fake.inr(debits), fake.inr(credits), fake.inr(close)]]

    if subtype == "bank_statement_export":  # XLSX / TXT export: one long table, no layout
        pg = Page(A4).add(T(36, 40, bank), T(36, 52, title or "Account Statement"),
                          KV(36, 70, left + right, size=8), TB(36, 200, widths, [head] + body, size=6.5), TB(36, 760, [120] * 4, summary))
        return Doc(title or "Statement", [pg], st.font)

    pages, i = [], 0
    for k in range(n_pages):
        pg = Page(A4)
        y = header(pg, st, bank, [f"{branch}, {p.city}", f"IFSC: {ifsc}   MICR: {rng.randint(10**8, 10**9 - 1)}"])
        if k == 0:
            if title:
                pg.add(centered(title, y + 16, 12, st, bold=True))
                y += 24
            pg.add(KV(36, y + 14, left, size=8, lw=78), KV(318, y + 14, right, size=8, lw=70))
            y += 14 + 6 * 12.4
            take = 20
        else:
            take = 30
        chunk = body[i:i + take]
        i += take
        pg.add(TB(36, y + 6, widths, [head] + chunk, size=6.5))
        y += 6 + (len(chunk) + 1) * 6.5 * 1.75
        pg.add(T(36, 820, f"Page {k + 1} of {n_pages}", size=6.5, color=GREY))
        if k == n_pages - 1:
            pg.add(TB(36, y + 14, [130, 130, 130, 133], summary, size=7.5))
            note = "This is a computer generated statement and does not require a signature."
            if subtype == "bank_statement_scan":
                pg.add(SEAL(470, y + 90, 32, f"{bank.upper()} {branch.upper()}"), SIGN(410, y + 120, 90, rng.random()),
                       T(410, y + 136, "Authorised Signatory", size=7.5))
            else:
                pg.add(T(36, y + 70, note, size=7, color=GREY))
        pages.append(pg)
    return Doc(title or "Statement", pages, st.font)


@template("cc_estatement")
def cc_statement(rng, st, subtype):
    p = fake.person(rng)
    code, bank = fake.bank(rng)
    product = rng.choice(CARD_PRODUCTS)
    v = st.variant
    last4 = rng.randint(1000, 9999)
    card = rng.choice([f"XXXX XXXX XXXX {last4}", f"{rng.randint(4000, 5599)} XXXX XXXX {last4}"])
    sd = fake.rand_date(rng, 2024, 2026)
    limit = rng.choice([50000, 75000, 100000, 150000, 200000, 300000, 500000])
    rows = []
    for _ in range(rng.randint(12, 26)):
        d = sd - timedelta(days=rng.randint(1, 30))
        pay = rng.random() < 0.12
        amt = rng.uniform(500, 40000) if pay else rng.uniform(80, 15000)
        rows.append((d, "PAYMENT RECEIVED - THANK YOU" if pay else rng.choice(MERCHANTS + ["MAKEMYTRIP", "UBER", "NETFLIX", "AJIO"]) + f" {p.city.upper()}", amt, pay))
    rows.sort(key=lambda r: r[0])
    total = max(0.0, sum(a for *_, a, pay in rows if not pay) - sum(a for *_, a, pay in rows if pay))
    mad = max(100.0, round(total * 0.05, 2))
    title = rng.choices(["Credit Card Statement", "Card Account Statement", f"Statement for your {bank} {product} Credit Card", None], [4, 2, 2, 1])[0]
    pg = Page(A4)
    y = header(pg, st, bank, [f"{product} Credit Card", "Credit Card Division"])
    if title:
        pg.add(centered(title, y + 16, 12, st, bold=True))
        y += 24
    idlabel = "Customer ID" if v in (1, 3) else "Customer Relationship No."
    pg.add(KV(36, y + 14, [("Name", p.name.upper()), ("", p.address_lines[0]), ("", p.address_lines[1]), ("", p.address_lines[2]),
                           (idlabel, str(rng.randint(10**7, 10**9)))], size=8, lw=110))
    y += 14 + 5 * 12.4 + 6
    pg.add(R(36, y, 523, 64, fill=(0.94, 0.95, 0.98), stroke=st.accent),
           KV(44, y + 14, [("Card Number", card), ("Statement Date", fake.fmt_date(sd, v)),
                           ("Payment Due Date", fake.fmt_date(sd + timedelta(days=18), v)), ("Credit Limit", fake.inr(limit))], size=8, lw=100),
           KV(300, y + 14, [("Total Amount Due", "Rs. " + fake.inr(total)), ("Minimum Amount Due", "Rs. " + fake.inr(mad)),
                            ("Available Credit Limit", fake.inr(max(0, limit - total))), ("Cash Limit", fake.inr(limit * 0.4))], size=8, lw=120))
    y += 80
    body = [[fake.fmt_date(d, v), desc, fake.inr(a) + (" Cr" if pay else "")] for d, desc, a, pay in rows]
    pg.add(TB(36, y, [70, 350, 103], [["Date", "Transaction Details", "Amount (in Rs.)"]] + body, size=7, align=[0, 0, 2]))
    y += (len(body) + 1) * 7 * 1.75 + 14
    pts = rng.randint(100, 9000)
    pg.add(TB(36, y, [130, 130, 130, 133], [["Reward Points: Opening", "Earned", "Redeemed", "Closing"],
                                            [str(pts), str(rng.randint(10, 600)), "0", str(pts + 50)]], size=7))
    if v in (0, 2):
        pg.add(P(36, 760, 523, 50, "Important: paying only the Minimum Amount Due every month would result in the repayment stretching into "
                                   "months or years, with interest charged on the outstanding balance. Please pay the Total Amount Due by the Payment Due Date.", size=6.5))
    return Doc(title or "Card statement", [pg], st.font)


@template("passbook_page")
def passbook(rng, st, subtype):
    p = fake.person(rng)
    code, bank = fake.bank(rng)
    branch = f"{rng.choice(fake.LOCALITIES)} Branch"
    pg = Page(PASSBOOK, bg=(0.98, 0.96, 0.9))
    if rng.random() < 0.4:  # first page: customer details, pasted photo, branch stamp
        pg.add(T(16, 22, bank.upper(), size=11, bold=True, color=st.accent), T(16, 33, f"{branch}, {p.city}", size=6.5, color=GREY))
        if rng.random() < 0.6:
            pg.add(T(16, 48, "SAVINGS BANK ACCOUNT PASS BOOK", size=8, bold=True))
        pg.add(KV(16, 66, [("Name", p.name.upper()), ("Address", p.address_lines[0]), ("", p.address_lines[1]), ("", p.address_lines[2]),
                           ("Customer ID", str(rng.randint(10**7, 10**9))), ("A/c No.", str(rng.randint(10**10, 10**14))),
                           ("IFSC", ids.fake_ifsc(rng, code)), ("Nominee", rng.choice(["Registered", fake.person(rng).name])),
                           ("Date of Opening", fake.fmt_date(fake.rand_date(rng, 2005, 2024), 1))], size=7, lw=70, vfont="cour"),
               PHOTO(340, 50, 66, 80), SEAL(395, 125, 24, f"{bank.upper()} {branch.upper()}"),
               SIGN(300, 230, 80, rng.random()), T(300, 246, "Branch Manager", size=6.5))
        return Doc("Passbook", [pg], "helv")
    cols, xs = ["Date", "Particulars", "Chq. No.", "Withdrawals", "Deposits", "Balance", "Init."], [12, 62, 180, 222, 280, 334, 392]
    for c, x in zip(cols, xs):
        pg.add(T(x + 2, 18, c, size=6.5, bold=True, color=st.accent))
    pg.add(L(12, 22, 418, 22, color=st.accent, lw=0.8))
    for r in range(1, 21):
        pg.add(L(12, 22 + r * 12, 418, 22 + r * 12, color=(0.8, 0.8, 0.75), lw=0.3))
    for x in xs[1:]:
        pg.add(L(x, 10, x, 262, color=(0.8, 0.8, 0.75), lw=0.3))
    bal, d = rng.uniform(1000, 90000), fake.rand_date(rng, 2023, 2026)
    for r in range(rng.randint(6, 18)):
        d += timedelta(days=rng.randint(0, 9))
        credit = rng.random() < 0.4
        amt = rng.uniform(100, 25000)
        bal = bal + amt if credit else max(100.0, bal - amt)
        jy, jx = 31 + r * 12 + rng.uniform(-1.5, 1.5), rng.uniform(-2, 2)
        vals = [d.strftime("%d-%m-%y"), rng.choice(["BY CASH", "TO CLG", "BY TRF", "INT.PD", "ATM WDL", "NEFT CR", "UPI/DR", "BY CLG", "TO SELF", "CHRGS"]),
                str(rng.randint(100000, 999999)) if rng.random() < 0.2 else "", "" if credit else f"{amt:.2f}", f"{amt:.2f}" if credit else "", f"{bal:.2f}", "SB"]
        for val, x in zip(vals, xs):
            pg.add(T(x + 3 + jx, jy, val, size=6.8, font="cour"))
    return Doc("Passbook", [pg], "helv")


@template("salary_slip_hrms", "salary_slip_scan")
def salary_slip(rng, st, subtype):
    co, p = fake.company(rng), fake.person(rng)
    mi = rng.randint(0, 11)
    month, year = fake.MONTHS[mi], rng.randint(2024, 2026)
    title = rng.choice([f"Payslip for the month of {month} {year}", f"Salary Slip - {month[:3]} {year}", "PAY SLIP",
                        f"Salary Statement for {month} {year}", f"PAYSLIP {month.upper()} {year}"])
    gross = rng.choice([25000, 32000, 45000, 60000, 85000, 120000, 175000]) * rng.uniform(0.9, 1.1)
    basic = round(gross * rng.uniform(0.4, 0.5))
    hra = round(basic * rng.choice([0.4, 0.5]))
    conv, lta = 1600, round(gross * 0.05)
    special = round(gross - basic - hra - conv - lta)
    pf, pt, tds = min(1800, round(basic * 0.12)), 200, round(max(0, gross - 50000) * rng.uniform(0.05, 0.15))
    earn = [("Basic Salary", basic), ("House Rent Allowance", hra), ("Conveyance Allowance", conv), ("Leave Travel Allowance", lta), ("Special Allowance", special)]
    ded = [("Provident Fund", pf), ("Professional Tax", pt), ("Income Tax (TDS)", tds)]
    rows = [["Earnings", "Amount (Rs.)", "Deductions", "Amount (Rs.)"]]
    for i in range(len(earn)):
        rows.append([earn[i][0], fake.inr(earn[i][1]), ded[i][0] if i < len(ded) else "", fake.inr(ded[i][1]) if i < len(ded) else ""])
    tot_e, tot_d = sum(a for _, a in earn), sum(a for _, a in ded)
    rows.append(["Gross Earnings", fake.inr(tot_e), "Total Deductions", fake.inr(tot_d)])
    net = tot_e - tot_d
    code, bank = fake.bank(rng)
    pg = Page(A4)
    y = header(pg, st, co.name, co.address_lines[:2])
    pg.add(centered(title, y + 16, 12, st, bold=True))
    y += 30
    pg.add(KV(36, y, [("Employee Code", f"E{rng.randint(1000, 99999)}"), ("Employee Name", p.name), ("Designation", rng.choice(["Executive", "Senior Engineer", "Manager", "Analyst", "Associate"])),
                      ("Department", rng.choice(["Operations", "Finance", "Engineering", "Sales", "HR"])), ("Date of Joining", fake.fmt_date(fake.rand_date(rng, 2012, 2025), st.variant))], size=8, lw=90),
           KV(310, y, [("PAN", p.pan), ("UAN", str(rng.randint(10**11, 10**12 - 1))), ("Bank Name", bank),
                       ("Bank A/c No.", str(rng.randint(10**10, 10**14))), ("Days Paid", str(rng.choice([30, 31, 28, 29])))], size=8, lw=80))
    y += 5 * 12.4 + 12
    pg.add(TB(36, y, [170, 92, 170, 91], rows, size=8, align=[0, 2, 0, 2]))
    y += len(rows) * 8 * 1.75 + 14
    pg.add(R(36, y, 523, 20, fill=(0.94, 0.94, 0.94), stroke=None), T(44, y + 13.5, f"Net Pay: Rs. {fake.inr(net)}", size=9.5, bold=True))
    pg.add(T(36, y + 36, f"Net Pay (in words): Rupees {fake.words(net)} Only", size=8))
    if subtype == "salary_slip_scan":
        pg.add(SEAL(470, y + 110, 30, co.name.upper()), SIGN(400, y + 130, 90, rng.random()), T(400, y + 146, "Authorised Signatory", size=7.5))
    else:
        pg.add(T(36, y + 70, "This is a system generated payslip and does not require signature.", size=7, color=GREY))
    return Doc(title, [pg], st.font)


@template("itr_v_acknowledgement")
def itr_v(rng, st, subtype):
    p = fake.person(rng)
    ay = rng.randint(2022, 2026)
    form = rng.choice(["ITR-1", "ITR-2", "ITR-3", "ITR-4"])
    income = rng.randint(300000, 4500000)
    tax = max(0, round((income - 700000) * 0.18))
    paid = tax + rng.randint(-20000, 30000)
    pg = Page(A4)
    pg.add(EMBLEM(297, 46, 30), centered("Government of India, Income Tax Department", 84, 9, st),
           centered(rng.choice(["INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT", "INCOME TAX RETURN ACKNOWLEDGEMENT", "ITR-V"]), 104, 12, st, bold=True),
           P(60, 112, 475, 26, "[Where the data of the Return of Income in Form ITR-1 (SAHAJ), ITR-2, ITR-3, ITR-4 (SUGAM), ITR-5, ITR-6, ITR-7 "
                               "filed and verified]", size=7, align=1),
           centered(f"Assessment Year {ay}-{str(ay + 1)[2:]}", 152, 10, st, bold=True))
    pg.add(KV(50, 176, [("PAN", p.pan), ("Name", p.name.upper()), ("Address", p.address_lines[0]), ("", p.address_lines[1]), ("", p.address_lines[2]),
                        ("Status", "Individual"), ("Form Number", form), ("e-Filing Acknowledgement Number", str(rng.randint(10**14, 10**15 - 1))),
                        ("Date of e-Filing", fake.fmt_date(fake.rand_date(rng, ay, ay), 0))], size=8.5, lw=170))
    rows = [["Particulars", "", "Amount (Rs.)"], ["Current Year business loss, if any", "1", "0"], ["Total Income", "2", fake.inr(income, 0)],
            ["Book Profit under MAT, where applicable", "3", "0"], ["Adjusted Total Income under AMT, where applicable", "4", "0"],
            ["Net tax payable", "5", fake.inr(tax, 0)], ["Interest and Fee Payable", "6", "0"], ["Total tax, interest and Fee payable", "7", fake.inr(tax, 0)],
            ["Taxes Paid", "8", fake.inr(paid, 0)], ["(+) Tax Payable / (-) Refundable (7-8)", "9", fake.inr(tax - paid, 0)],
            ["Accreted Income as per section 115TD", "10", "0"]]
    pg.add(TB(50, 330, [330, 40, 125], rows, size=8, align=[0, 0, 2]))
    pg.add(P(50, 560, 495, 50, f"This return has been digitally signed / verified through Aadhaar OTP by {p.name.upper()} having PAN {p.pan} "
                               f"from IP address 103.{rng.randint(1, 250)}.{rng.randint(1, 250)}.{rng.randint(1, 250)} on {fake.fmt_date(fake.rand_date(rng, ay, ay), 1)} at {p.city}.", size=8),
           T(50, 640, "System Generated", size=8, bold=True), BARS(50, 652, 200, 30, rng.random()), QR(470, 640, 70, rng.random()))
    return Doc("ITR-V", [pg], st.font)


@template("itr_full_return")
def itr_full(rng, st, subtype):
    p = fake.person(rng)
    ay = rng.randint(2022, 2026)
    f = Flow(st)
    f.page.add(EMBLEM(297, 40, 26))
    f.y = 66
    f.heading("FORM ITR-1 SAHAJ" if rng.random() < 0.6 else "FORM ITR-4 SUGAM", 13)
    f.para("INDIAN INCOME TAX RETURN [For individuals being a resident (other than not ordinarily resident) having total income up to "
           "Rs. 50 lakh] (See rule 12 of the Income-tax Rules, 1962)", 8, align=1)
    f.heading(f"Assessment Year {ay}-{str(ay + 1)[2:]}", 10)
    f.heading("PART A  GENERAL INFORMATION", 9.5, center=False)
    y = f.need(150)
    f.page.add(KV(f.x, y + 10, [("First Name", p.first.upper()), ("Last Name", p.last.upper()), ("PAN", p.pan), ("Date of Birth", fake.fmt_date(p.dob, 1)),
                                ("Aadhaar Number", fake.aadhaar_shown(rng, p.aadhaar, 0.5)), ("Mobile No.", p.mobile), ("Email Address", p.email),
                                ("Flat/Door/Block No.", p.house), ("Road/Street", p.street), ("Town/City/District", p.city), ("PIN Code", p.pin)], size=8, lw=150))
    f.heading("PART B  GROSS TOTAL INCOME", 9.5, center=False)
    sal = rng.randint(300000, 2500000)
    rows = [["", "Particulars", "Amount (Rs.)"], ["B1", "Gross Salary", fake.inr(sal, 0)], ["B1(ii)", "Allowances to the extent exempt u/s 10", fake.inr(rng.randint(0, 90000), 0)],
            ["B1(iii)", "Standard deduction u/s 16(ia)", "50,000"], ["B2", "Income from one house property", "0"],
            ["B3", "Income from other sources", fake.inr(rng.randint(0, 80000), 0)], ["B4", "Gross Total Income (B1+B2+B3)", fake.inr(sal, 0)]]
    y = f.need(len(rows) * 15 + 10)
    f.page.add(TB(f.x, y, [50, 330, 107], rows, size=8, align=[0, 0, 2]))
    f.heading("PART C  DEDUCTIONS AND TAXABLE TOTAL INCOME", 9.5, center=False)
    rows = [["Section", "Amount (Rs.)"], ["80C", fake.inr(rng.randint(0, 150000), 0)], ["80D", fake.inr(rng.randint(0, 25000), 0)], ["80TTA", fake.inr(rng.randint(0, 10000), 0)]]
    y = f.need(len(rows) * 15 + 10)
    f.page.add(TB(f.x, y, [200, 120], rows, size=8, align=[0, 2]))
    f.heading("VERIFICATION", 9.5, center=False)
    f.para(f"I, {p.name.upper()}, son/daughter of {p.father.upper()}, solemnly declare that to the best of my knowledge and belief, the information "
           f"given in the return is correct and complete and is in accordance with the provisions of the Income-tax Act, 1961.", 8.5)
    return Doc("ITR", f.pages, st.font)


@template("gst_reg06_certificate")
def gst_certificate(rng, st, subtype):
    co = fake.company(rng)
    trade = co.name.split(" Private")[0].split(" Pvt")[0].split(" Limited")[0]
    pg = Page(A4)
    pg.add(EMBLEM(297, 40, 26), centered("Government of India", 74, 10, st, bold=True), centered("Form GST REG-06", 92, 11, st, bold=True),
           centered("[See Rule 10(1)]", 106, 8, st), centered("Registration Certificate", 126, 13, st, bold=True),
           centered(f"Registration Number : {co.gstin}", 146, 10, st, bold=True))
    rows = [["1.", "Legal Name", co.name.upper()], ["2.", "Trade Name, if any", trade.upper()], ["3.", "Additional trade names, if any", ""],
            ["4.", "Constitution of Business", "Private Limited Company" if "Private" in co.name or "Pvt" in co.name else "Public Limited Company"],
            ["5.", "Address of Principal Place of Business", co.address_lines[0]], ["", "", co.address_lines[1] + ", " + co.address_lines[2]],
            ["6.", "Date of Liability", fake.fmt_date(fake.rand_date(rng, 2017, 2024), 0)], ["7.", "Date of Validity", "From  " + fake.fmt_date(fake.rand_date(rng, 2017, 2024), 0) + "   To  Not Applicable"],
            ["8.", "Type of Registration", "Regular"], ["9.", "Particulars of Approving Authority", "Signature, Name, Designation, Jurisdictional Office"],
            ["10.", "Date of issue of Certificate", fake.fmt_date(fake.rand_date(rng, 2017, 2025), 0)]]
    pg.add(TB(40, 170, [30, 200, 285], rows, size=7.8, header=False))
    pg.add(T(40, 400, "Signature Not Verified", size=7, color=GREY), T(40, 412, "Digitally signed by DS GOODS AND SERVICES TAX NETWORK", size=7, color=GREY),
           P(40, 440, 515, 40, "Note: The registration certificate is required to be prominently displayed at all places of business in the State.", size=8))
    p2 = Page(A4)
    p2.add(centered("Annexure B", 60, 12, st, bold=True), centered(f"GSTIN : {co.gstin}", 80, 9, st), centered(f"Legal Name : {co.name.upper()}", 94, 9, st),
           centered("Details of Managing / Authorized Partners / Karta", 118, 10, st, bold=True))
    y = 140
    for i in range(rng.randint(1, 3)):
        d = fake.person(rng)
        p2.add(KV(50, y, [("Name", d.name), ("Designation/Status", rng.choice(["Director", "Managing Director", "Whole-time Director"])),
                          ("Resident of State", d.state)], size=8, lw=120))
        y += 52
    return Doc("GST Registration Certificate", [pg, p2], st.font)


@template("gst_return")
def gst_return(rng, st, subtype):
    co = fake.company(rng)
    year, month = rng.randint(2023, 2026), fake.MONTHS[rng.randint(0, 11)]
    pg = Page(A4)
    if rng.random() < 0.55:
        pg.add(centered("FORM GSTR-3B", 50, 13, st, bold=True), centered("[See rule 61(5)]", 64, 8, st),
               KV(40, 90, [("Year", f"{year}-{str(year + 1)[2:]}"), ("Period", month), ("1. GSTIN", co.gstin), ("2(a). Legal name of the registered person", co.name.upper()),
                           ("2(b). Trade name, if any", co.name.split()[0].upper()), ("2(c). ARN", f"AA{co.gstin[:2]}{rng.randint(10**11, 10**12)}"),
                           ("2(d). Date of ARN", fake.fmt_date(fake.rand_date(rng, year, year), 0))], size=8, lw=200))
        v = lambda: fake.inr(rng.uniform(0, 4000000))
        rows = [["Nature of Supplies", "Total Taxable value", "Integrated Tax", "Central Tax", "State/UT Tax", "Cess"],
                ["(a) Outward taxable supplies (other than zero rated, nil rated and exempted)", v(), v(), v(), v(), "0.00"],
                ["(b) Outward taxable supplies (zero rated)", v(), v(), "0.00", "0.00", "0.00"],
                ["(c) Other outward supplies (nil rated, exempted)", v(), "0.00", "0.00", "0.00", "0.00"],
                ["(d) Inward supplies (liable to reverse charge)", v(), v(), v(), v(), "0.00"],
                ["(e) Non-GST outward supplies", v(), "0.00", "0.00", "0.00", "0.00"]]
        pg.add(T(40, 210, "3.1 Details of Outward Supplies and inward supplies liable to reverse charge", size=8.5, bold=True),
               TB(40, 218, [190, 70, 65, 60, 65, 65], rows, size=6.5),
               T(40, 360, "4. Eligible ITC", size=8.5, bold=True),
               TB(40, 368, [190, 85, 80, 80, 80], [["Details", "Integrated Tax", "Central Tax", "State/UT Tax", "Cess"],
                                                   ["(A) ITC Available (whether in full or part)", v(), v(), v(), "0.00"],
                                                   ["(B) ITC Reversed", "0.00", v(), v(), "0.00"], ["(C) Net ITC Available (A) - (B)", v(), v(), v(), "0.00"]], size=6.5),
               T(40, 470, "6.1 Payment of tax", size=8.5, bold=True),
               TB(40, 478, [130, 90, 90, 90, 115], [["Description", "Tax payable", "Paid through ITC", "Tax paid in cash", "Interest / Late Fee"],
                                                    ["Integrated Tax", v(), v(), v(), "0.00"], ["Central Tax", v(), v(), v(), "0.00"], ["State/UT Tax", v(), v(), v(), "0.00"]], size=6.5))
        return Doc("GSTR-3B", [pg], st.font)
    pg.add(centered("FORM GSTR-1", 50, 13, st, bold=True), centered("Details of outward supplies of goods or services", 64, 8.5, st),
           KV(40, 90, [("GSTIN", co.gstin), ("Legal name of the registered person", co.name.upper()), ("Tax period", f"{month} {year}")], size=8, lw=200))
    rows = [["GSTIN/UIN of Recipient", "Invoice No.", "Invoice date", "Invoice Value", "Place Of Supply", "Rate", "Taxable Value"]]
    for _ in range(rng.randint(10, 28)):
        val = rng.uniform(5000, 900000)
        rows.append([ids.fake_gstin(rng), f"INV/{rng.randint(1, 9999)}", fake.fmt_date(fake.rand_date(rng, year, year), 0), fake.inr(val * 1.18),
                     f"{rng.randint(1, 37):02d}-{rng.choice(fake.STATES)[0]}", rng.choice(["5%", "12%", "18%", "28%"]), fake.inr(val)])
    pg.add(T(40, 150, "4A, 4B, 4C, 6B, 6C - B2B Invoices", size=8.5, bold=True), TB(40, 158, [100, 60, 60, 75, 95, 40, 85], rows, size=6.5))
    return Doc("GSTR-1", [pg], st.font)


@template("audited_financials")
def audited(rng, st, subtype):
    co = fake.company(rng)
    year = rng.randint(2022, 2026)
    firm = f"{rng.choice(['Mehta', 'Shah', 'Iyer', 'Gupta', 'Rao', 'Kapoor', 'Joshi', 'Menon'])} & {rng.choice(['Associates', 'Co.', 'Partners'])}"
    frn, memno = f"{rng.randint(100000, 199999)}{rng.choice('WSNE')}", rng.randint(100000, 199999)
    udin = f"{str(year)[2:]}{memno}{''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(6))}{rng.randint(1000, 9999)}"
    pages = []
    if st.variant != 2 or rng.random() < 0.5:
        f = Flow(st)
        f.heading("INDEPENDENT AUDITOR'S REPORT", 12)
        f.para(f"To the Members of {co.name}", 9.5, bold=True, align=0)
        f.heading("Report on the Audit of the Standalone Financial Statements", 10, center=False)
        f.heading("Opinion", 9.5, center=False)
        f.para(f"We have audited the accompanying standalone financial statements of {co.name} (\"the Company\"), which comprise the Balance Sheet "
               f"as at 31st March {year}, the Statement of Profit and Loss and the Statement of Cash Flows for the year then ended, and notes to the "
               f"financial statements, including a summary of significant accounting policies and other explanatory information.")
        f.para("In our opinion and to the best of our information and according to the explanations given to us, the aforesaid standalone financial "
               "statements give the information required by the Companies Act, 2013 in the manner so required and give a true and fair view in "
               f"conformity with the accounting principles generally accepted in India, of the state of affairs of the Company as at 31st March {year}, "
               "and its profit and its cash flows for the year ended on that date.")
        f.heading("Basis for Opinion", 9.5, center=False)
        f.para("We conducted our audit in accordance with the Standards on Auditing (SAs) specified under section 143(10) of the Companies Act, 2013. "
               "Our responsibilities under those Standards are further described in the Auditor's Responsibilities section of our report.")
        f.heading("Responsibilities of Management for the Standalone Financial Statements", 9.5, center=False)
        f.para("The Company's Board of Directors is responsible for the matters stated in section 134(5) of the Act with respect to the preparation "
               "of these standalone financial statements that give a true and fair view of the financial position and financial performance.")
        y = f.need(150)
        f.page.add(T(f.x, y + 12, f"For {firm}", size=9, bold=True), T(f.x, y + 24, "Chartered Accountants", size=8.5),
                   T(f.x, y + 36, f"Firm's Registration No.: {frn}", size=8.5), SIGN(f.x, y + 60, 100, rng.random()),
                   T(f.x, y + 78, f"CA {fake.person(rng).name}, Partner", size=8.5), T(f.x, y + 90, f"Membership No.: {memno}", size=8.5),
                   T(f.x, y + 102, f"UDIN: {udin}", size=8.5), T(f.x, y + 114, f"Place: {co.city}", size=8.5),
                   SEAL(f.x + 330, y + 60, 34, f"{firm.upper()} CHARTERED ACCOUNTANTS"))
        pages += f.pages
    m = lambda lo, hi: fake.inr(rng.uniform(lo, hi), 0)
    pg = Page(A4)
    y = header(pg, st, co.name, [f"CIN: {co.cin}"])
    pg.add(centered(f"Balance Sheet as at 31st March {year}", y + 14, 11, st, bold=True), T(440, y + 30, "(Amount in Rs.)", size=7, color=GREY))
    rows = [["Particulars", "Note No.", f"As at 31.03.{year}", f"As at 31.03.{year - 1}"], ["I. EQUITY AND LIABILITIES", "", "", ""],
            ["(1) Shareholders' funds", "", "", ""], ["  (a) Share capital", "2", m(1e5, 5e7), m(1e5, 5e7)], ["  (b) Reserves and surplus", "3", m(1e6, 9e8), m(1e6, 9e8)],
            ["(2) Non-current liabilities", "", "", ""], ["  (a) Long-term borrowings", "4", m(0, 4e8), m(0, 4e8)],
            ["(3) Current liabilities", "", "", ""], ["  (a) Short-term borrowings", "5", m(0, 2e8), m(0, 2e8)], ["  (b) Trade payables", "6", m(1e5, 3e8), m(1e5, 3e8)],
            ["  (c) Other current liabilities", "7", m(1e5, 9e7), m(1e5, 9e7)], ["TOTAL", "", m(1e7, 2e9), m(1e7, 2e9)], ["II. ASSETS", "", "", ""],
            ["(1) Non-current assets", "", "", ""], ["  (a) Property, Plant and Equipment", "8", m(1e6, 8e8), m(1e6, 8e8)], ["  (b) Non-current investments", "9", m(0, 1e8), m(0, 1e8)],
            ["(2) Current assets", "", "", ""], ["  (a) Inventories", "10", m(1e5, 3e8), m(1e5, 3e8)], ["  (b) Trade receivables", "11", m(1e5, 3e8), m(1e5, 3e8)],
            ["  (c) Cash and cash equivalents", "12", m(1e4, 9e7), m(1e4, 9e7)], ["  (d) Short-term loans and advances", "13", m(0, 5e7), m(0, 5e7)],
            ["TOTAL", "", m(1e7, 2e9), m(1e7, 2e9)]]
    pg.add(TB(36, y + 40, [250, 50, 111, 112], rows, size=7.5, align=[0, 0, 2, 2], ruled=st.variant != 1))
    pages.append(pg)
    pg = Page(A4)
    pg.add(centered(f"Statement of Profit and Loss for the year ended 31st March {year}", 60, 11, st, bold=True))
    rows = [["Particulars", "Note No.", f"FY {year - 1}-{str(year)[2:]}", f"FY {year - 2}-{str(year - 1)[2:]}"], ["I. Revenue from operations", "14", m(1e7, 3e9), m(1e7, 3e9)],
            ["II. Other income", "15", m(0, 5e7), m(0, 5e7)], ["III. Total Income (I + II)", "", m(1e7, 3e9), m(1e7, 3e9)], ["IV. Expenses:", "", "", ""],
            ["  Cost of materials consumed", "16", m(1e6, 1e9), m(1e6, 1e9)], ["  Employee benefits expense", "17", m(1e6, 4e8), m(1e6, 4e8)],
            ["  Finance costs", "18", m(0, 9e7), m(0, 9e7)], ["  Depreciation and amortisation expense", "8", m(1e5, 9e7), m(1e5, 9e7)],
            ["  Other expenses", "19", m(1e6, 3e8), m(1e6, 3e8)], ["  Total expenses (IV)", "", m(1e7, 2e9), m(1e7, 2e9)],
            ["V. Profit before tax (III - IV)", "", m(1e5, 4e8), m(1e5, 4e8)], ["VI. Tax expense: Current tax", "", m(0, 1e8), m(0, 1e8)],
            ["  Deferred tax", "", m(0, 1e7), m(0, 1e7)], ["VII. Profit for the year", "", m(1e5, 3e8), m(1e5, 3e8)],
            ["VIII. Earnings per equity share: Basic and Diluted (Rs.)", "20", f"{rng.uniform(1, 90):.2f}", f"{rng.uniform(1, 90):.2f}"]]
    pg.add(TB(36, 80, [250, 50, 111, 112], rows, size=7.5, align=[0, 0, 2, 2]))
    pg.add(T(36, 420, "As per our report of even date", size=8), T(36, 432, f"For {firm}, Chartered Accountants (FRN {frn})", size=8),
           T(36, 444, f"UDIN: {udin}", size=8), SIGN(36, 470, 90, rng.random()),
           T(320, 420, "For and on behalf of the Board of Directors", size=8, bold=True), SIGN(320, 450, 80, rng.random()), SIGN(440, 450, 80, rng.random()),
           T(320, 466, f"Director (DIN: 0{rng.randint(1000000, 9999999)})", size=7.5), T(440, 466, f"Director (DIN: 0{rng.randint(1000000, 9999999)})", size=7.5))
    pages.append(pg)
    return Doc("Audited Financial Statements", pages, st.font)
