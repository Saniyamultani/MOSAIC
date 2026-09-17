"""Shared text helpers used by the ingestion, entity and skeptic agents."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

BRANDS = [
    "Samsung", "Apple", "Sony", "LG", "OnePlus", "Xiaomi", "Redmi", "Realme", "Vivo", "Oppo",
    "Nothing", "Motorola", "Google", "Dell", "HP", "Lenovo", "Asus", "Acer", "MSI", "TP-Link",
    "Netgear", "D-Link", "Bosch", "Whirlpool", "Philips", "Haier", "Godrej", "IFB", "Voltas",
    "Daikin", "Blue Star", "Canon", "Nikon", "GoPro", "JBL", "boAt", "Noise", "Amazfit",
    "Mi", "Honor", "Panasonic", "Toshiba", "Seagate", "Western Digital", "Logitech", "Razer",
]

RETAILERS = [
    "Amazon", "Flipkart", "Croma", "Reliance Digital", "Vijay Sales", "Tata Cliq", "Myntra",
    "Apple Store", "Samsung Shop", "Best Buy", "Sangeetha", "Poorvika", "JioMart", "Nykaa",
]

PAYMENT_METHODS = [
    "HDFC", "ICICI", "SBI", "Axis", "Kotak", "IndusInd", "American Express", "Amex",
    "Visa", "Mastercard", "RuPay", "UPI", "Paytm", "PhonePe", "Google Pay",
]

SUBSCRIPTION_BRANDS = [
    "Netflix", "Spotify", "YouTube Premium", "Amazon Prime", "Disney+ Hotstar", "Hotstar",
    "Apple One", "iCloud", "Google One", "Adobe", "Microsoft 365", "Notion", "Zoho", "Jio",
    "Airtel", "Sony LIV", "Zee5",
]

CURRENCY_SYMBOLS = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP"}

PRICE_RE = re.compile(
    r"(?:(₹|\$|€|£)|\b(?:rs\.?|inr|usd|eur|gbp)\s*)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)

# Model codes such as SM-S926B, RT-AX55, XR-55A80K, A2650
MODEL_CODE_RE = re.compile(r"\b(?=[A-Z0-9-]{4,20}\b)(?=[A-Z0-9-]*\d)[A-Z]{1,4}[A-Z0-9]*(?:-[A-Z0-9]+)+\b")
# Consumer model names such as "Galaxy S26 Ultra", "iPhone 17 Pro"
MODEL_NAME_RE = re.compile(
    r"\b((?:Galaxy|iPhone|iPad|MacBook|Pixel|OnePlus|Bravia|Inspiron|Ideapad|ThinkPad|"
    r"Archer|Nord|Redmi|Note|Zenbook|Vivobook|Air|Pro)\s+[A-Za-z0-9+-]*[A-Za-z0-9+](?:\s+(?:Pro|Ultra|Plus|Max|Lite|FE|5G))?)",
    re.IGNORECASE,
)

DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "%Y-%m-%d"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), "%d/%m/%Y"),
    (re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b"), "%d-%m-%Y"),
]
MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"], start=1)
}
MONTHS.update({m[:3].lower(): i for m, i in list(MONTHS.items())})
TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9}),?\s+(\d{4})\b|\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b"
)

DURATION_RE = re.compile(r"\b(\d{1,2})\s*(year|yr|month|mo)s?\b", re.IGNORECASE)


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def normalize_key(value: str) -> str:
    """Canonical key for entity resolution: lowercase, alphanumeric only."""
    value = strip_accents(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def tokens(value: str) -> set[str]:
    return set(normalize_key(value).split())


def find_first(haystack: str, needles: list[str]) -> str | None:
    low = haystack.lower()
    best: tuple[int, str] | None = None
    for needle in needles:
        idx = low.find(needle.lower())
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, needle)
    return best[1] if best else None


def find_all(haystack: str, needles: list[str]) -> list[str]:
    low = haystack.lower()
    return [n for n in needles if n.lower() in low]


def extract_price(text: str) -> tuple[float | None, str | None]:
    match = PRICE_RE.search(text)
    if not match:
        return None, None
    symbol, amount = match.group(1), match.group(2)
    currency = CURRENCY_SYMBOLS.get(symbol or "", None)
    if currency is None:
        head = text[max(0, match.start()) : match.start() + 5].upper()
        for code in ("INR", "USD", "EUR", "GBP", "RS"):
            if code in head:
                currency = "INR" if code == "RS" else code
                break
    try:
        return float(amount.replace(",", "")), currency or "INR"
    except ValueError:
        return None, currency


def extract_date(text: str) -> str | None:
    for pattern, fmt in DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                return datetime.strptime(m.group(0), fmt).date().isoformat()
            except ValueError:
                continue
    m = TEXT_DATE_RE.search(text)
    if m:
        if m.group(1):
            day, month_name, year = m.group(1), m.group(2), m.group(3)
        else:
            month_name, day, year = m.group(4), m.group(5), m.group(6)
        month = MONTHS.get(month_name.lower()[:3])
        if month:
            try:
                return date(int(year), month, int(day)).isoformat()
            except ValueError:
                return None
    return None


# "Plan number SCP-IN-88213" is a reference, not a model code.
REFERENCE_CONTEXT = re.compile(
    r"\b(?:plan|order|account|invoice|reference|policy|serial|ticket|receipt|bill)\s*"
    r"(?:number|no\.?|#|id)?\s*[:\-]?\s*$",
    re.IGNORECASE,
)


def extract_model_codes(text: str) -> list[str]:
    codes = set()
    for match in MODEL_CODE_RE.finditer(text):
        prefix = text[max(0, match.start() - 40) : match.start()]
        if REFERENCE_CONTEXT.search(prefix):
            continue
        codes.add(match.group(0).strip())
    return sorted(codes)


def extract_model_name(text: str) -> str | None:
    m = MODEL_NAME_RE.search(text)
    return " ".join(m.group(1).split()) if m else None


def extract_duration_months(text: str) -> int | None:
    m = DURATION_RE.search(text)
    if not m:
        return None
    value, unit = int(m.group(1)), m.group(2).lower()
    return value * 12 if unit.startswith(("year", "yr")) else value


def add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
                          31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def token_overlap(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
