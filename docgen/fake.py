"""Fake Indian people, companies and amounts for the templates.

Names come from Faker's en_IN locale, identifiers from common/identifiers.py.
Everything is random and tied to no real person.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from faker import Faker

from common import identifiers as ids

# (state, vehicle registration code, GST state code, cities, first PIN digit)
STATES = [
    ("Maharashtra", "MH", "27", ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane"], "4"),
    ("Karnataka", "KA", "29", ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi"], "5"),
    ("Tamil Nadu", "TN", "33", ["Chennai", "Coimbatore", "Madurai"], "6"),
    ("Delhi", "DL", "07", ["New Delhi"], "1"),
    ("Gujarat", "GJ", "24", ["Ahmedabad", "Surat", "Vadodara"], "3"),
    ("Uttar Pradesh", "UP", "09", ["Lucknow", "Kanpur", "Noida"], "2"),
    ("West Bengal", "WB", "19", ["Kolkata", "Howrah"], "7"),
    ("Telangana", "TS", "36", ["Hyderabad", "Warangal"], "5"),
    ("Rajasthan", "RJ", "08", ["Jaipur", "Udaipur", "Jodhpur"], "3"),
    ("Kerala", "KL", "32", ["Kochi", "Thiruvananthapuram"], "6"),
]
STREETS = ["M.G. Road", "Station Road", "Link Road", "Nehru Marg", "Shivaji Path", "Park Street", "Ring Road",
           "Gandhi Road", "Church Street", "Temple Road", "Lake View Road", "Market Road", "S.V. Road"]
LOCALITIES = ["Andheri East", "Kothrud", "Indiranagar", "Adyar", "Saket", "Navrangpura", "Gomti Nagar", "Salt Lake",
              "Banjara Hills", "Malviya Nagar", "Kakkanad", "Shivaji Nagar", "Vile Parle West", "Jayanagar", "Anna Nagar"]
BUILDINGS = ["Sai Krupa", "Shanti Niwas", "Green Park", "Lotus Heights", "Om Residency", "Sunrise Apartments",
             "Ganga Vihar", "Silver Oak", "Krishna Kunj", "Mangal Murti"]
CO_PREFIX = ["Shree Ganesh", "Apex", "Vertex", "Sai", "Lakshmi", "Bharat", "Navyug", "Orion", "Sunrise", "Tatva",
             "Kaveri", "Pinnacle", "Indus", "Medha", "Vardhman", "Aarohi"]
CO_NOUN = ["Textiles", "Infosolutions", "Engineering Works", "Agro Foods", "Logistics", "Pharma", "Polymers",
           "Constructions", "Traders", "Software", "Auto Components", "Packaging"]
CO_SUFFIX = ["Private Limited", "Pvt. Ltd.", "Limited"]
NIC = ["72900", "17110", "15400", "60231", "24230", "45200", "51909", "29130"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]

_fk = Faker("en_IN")


def _latin1(s: str) -> str:
    return s.encode("latin-1", "ignore").decode("latin-1")


@dataclass
class Person:
    first: str
    last: str
    gender: str
    father: str
    mother: str
    dob: date
    house: str
    street: str
    locality: str
    city: str
    state: str
    rto: str
    gst_state: str
    pin: str
    mobile: str
    email: str
    pan: str
    aadhaar: str

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def address_lines(self) -> list[str]:
        return [self.house + ", " + self.street, self.locality + ", " + self.city, f"{self.state} - {self.pin}"]

    @property
    def address(self) -> str:
        return ", ".join(self.address_lines)


@dataclass
class Company:
    name: str
    cin: str
    pan: str
    gstin: str
    address_lines: list[str]
    city: str
    state: str
    incorporated: date

    @property
    def address(self) -> str:
        return ", ".join(self.address_lines)


def person(rng: random.Random) -> Person:
    _fk.seed_instance(rng.randint(0, 10**9))
    gender = rng.choice(["MALE", "FEMALE"])
    first = _latin1(_fk.first_name_male() if gender == "MALE" else _fk.first_name_female())
    last = _latin1(_fk.last_name())
    state, rto, gst, cities, pin0 = rng.choice(STATES)
    city = rng.choice(cities)
    house = f"{rng.choice(['Flat No.', 'Room No.', 'House No.', 'B-', 'A-'])} {rng.randint(1, 1404)}, {rng.choice(BUILDINGS)}"
    return Person(
        first=first, last=last, gender=gender,
        father=f"{_latin1(_fk.first_name_male())} {last}", mother=f"{_latin1(_fk.first_name_female())} {last}",
        dob=rand_date(rng, 1965, 2004), house=house, street=rng.choice(STREETS), locality=rng.choice(LOCALITIES),
        city=city, state=state, rto=rto, gst_state=gst, pin=pin0 + f"{rng.randint(0, 99999):05d}",
        mobile=f"{rng.choice('6789')}{rng.randint(0, 999_999_999):09d}",
        email=f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@{rng.choice(['gmail.com', 'yahoo.co.in', 'outlook.com'])}",
        pan=ids.fake_pan(rng, "P", last[0]), aadhaar=ids.fake_aadhaar(rng),
    )


def company(rng: random.Random) -> Company:
    state, rto, gst, cities, pin0 = rng.choice(STATES)
    city = rng.choice(cities)
    name = f"{rng.choice(CO_PREFIX)} {rng.choice(CO_NOUN)} {rng.choice(CO_SUFFIX)}"
    inc = rand_date(rng, 1995, 2023)
    pan = ids.fake_pan(rng, "C", name[0])
    return Company(
        name=name, cin=f"U{rng.choice(NIC)}{rto}{inc.year}PTC{rng.randint(0, 999999):06d}", pan=pan,
        gstin=ids.fake_gstin(rng, gst, pan),
        address_lines=[f"Unit {rng.randint(1, 450)}, {rng.choice(BUILDINGS)} Industrial Estate",
                       f"{rng.choice(STREETS)}, {rng.choice(LOCALITIES)}", f"{city}, {state} - {pin0}{rng.randint(0, 99999):05d}"],
        city=city, state=state, incorporated=inc,
    )


def bank(rng: random.Random) -> tuple[str, str]:
    code = rng.choice(list(ids.BANK_CODES))
    return code, ids.BANK_CODES[code]


def aadhaar_shown(rng: random.Random, aadhaar: str, masked_share: float) -> str:
    """The Aadhaar number as printed: full, or UIDAI-style masked (last 4 digits).
    Both appear on cards and on forms, so neither form alone marks a KYC card (D23)."""
    if rng.random() < masked_share:
        return "XXXX XXXX " + aadhaar[-4:]
    return f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}"


def rand_date(rng: random.Random, y0: int, y1: int) -> date:
    start = date(y0, 1, 1)
    return start + timedelta(days=rng.randint(0, (date(y1, 12, 28) - start).days))


def fmt_date(d: date, variant: int) -> str:
    return d.strftime(["%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d.%m.%Y"][variant % 4])


def inr(x: float, decimals: int = 2) -> str:
    """Indian digit grouping: 12,34,567.89"""
    neg, x = x < 0, abs(x)
    whole, _, frac = f"{x:.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail, groups = whole[:-3], whole[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(([head] if head else []) + groups + [tail])
    return ("-" if neg else "") + whole + ("." + frac if frac else "")


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def words(n: int) -> str:
    """Rupees in words, Indian style: 1,25,000 -> One Lakh Twenty Five Thousand"""
    n = int(n)
    if n == 0:
        return "Zero"
    parts = []
    for div, name in ((10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand"), (100, "Hundred")):
        if n >= div:
            parts.append(f"{words(n // div) if div == 10**7 else _two(n // div)} {name}")
            n %= div
    if n:
        parts.append(_two(n))
    return " ".join(parts)
