"""Deterministic checks on LLM answers: money, numeric facts and citations."""
import re

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NUM = r"\d[\d.,\s ٬٫]*\d|\d"
_CURRENCY = r"(?:US\$|USD|\$|dollars?|dólares|dolares|دولار)"
_MONEY = re.compile(rf"(?:{_CURRENCY}\s?(?P<a>{_NUM}))|(?:(?P<b>{_NUM})\s?{_CURRENCY})", re.IGNORECASE)

# NOTE: English/Spanish/Arabic unit words -> canonical unit; extend when adding languages
_UNITS = {
    "%": "%", "percent": "%", "per cent": "%", "por ciento": "%", "بالمئة": "%", "في المئة": "%",
    "week": "week", "weeks": "week", "semana": "week", "semanas": "week", "أسبوع": "week", "أسابيع": "week",
    "day": "day", "days": "day", "día": "day", "días": "day", "dia": "day", "dias": "day", "يوم": "day", "أيام": "day",
    "month": "month", "months": "month", "mes": "month", "meses": "month", "شهر": "month", "أشهر": "month",
    "year": "year", "years": "year", "año": "year", "años": "year", "سنة": "year", "سنوات": "year",
    "hour": "hour", "hours": "hour", "hora": "hour", "horas": "hour", "ساعة": "hour", "ساعات": "hour",
    "night": "night", "nights": "night", "noche": "night", "noches": "night", "ليلة": "night", "ليال": "night",
    "session": "session", "sessions": "session", "sesión": "session", "sesiones": "session", "جلسة": "session", "جلسات": "session",
}
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "eleven": 11, "twelve": 12, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
          "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "doce": 12}
_UNIT_RE = "|".join(sorted(map(re.escape, _UNITS), key=len, reverse=True))
_QTY = re.compile(rf"(?<![\w.,])(?P<n>\d+(?:[.,]\d+)?|{'|'.join(_WORDS)})\s*[-–]?\s*(?P<u>{_UNIT_RE})(?!\w)", re.IGNORECASE)


def _to_int(raw: str) -> int | None:
    digits = re.sub(r"[\s ]", "", raw)
    # NOTE: a 2-digit tail after a separator is cents ("18,995.00", "18.995,00"); 3 digits is a thousands group
    digits = re.sub(r"[.,٫]\d{2}$", "", digits)
    digits = re.sub(r"[.,٬٫]", "", digits)
    return int(digits) if digits.isdigit() else None


def money_amounts(text: str) -> set[int]:
    text = text.translate(_ARABIC_DIGITS)
    out = set()
    for m in _MONEY.finditer(text):
        n = _to_int(m.group("a") or m.group("b"))
        if n is not None:
            out.add(n)
    return out


def quantities(text: str) -> set[tuple[float, str]]:
    """Numbers with a unit, e.g. "3-week" -> (3, "week"), "85%" -> (85, "%"), "tres semanas" -> (3, "week")."""
    out = set()
    for m in _QTY.finditer(text.translate(_ARABIC_DIGITS)):
        raw, unit = m.group("n").lower(), _UNITS[m.group("u").lower()]
        out.add((float(_WORDS.get(raw, raw.replace(",", "."))), unit))
    return out


def unsupported_facts(answer: str, evidence: list[str]) -> list[str]:
    """Money amounts and unit quantities in the answer that appear nowhere in the evidence."""
    joined = "\n".join(evidence)
    money = sorted(money_amounts(answer) - money_amounts(joined))
    qty = sorted(quantities(answer) - quantities(joined))
    return [f"${n:,}" for n in money] + [f"{n:g}{u if u == '%' else ' ' + u}" for n, u in qty]


def valid_citations(cited: list[str], retrieved_ids: set[str]) -> list[str]:
    return [c for c in dict.fromkeys(cited) if c in retrieved_ids]


if __name__ == "__main__":
    assert money_amounts("Out-Patient $18,995 and In-Patient $30,000") == {18995, 30000}
    assert money_amounts("cuesta 18.995 USD") == {18995}
    assert money_amounts("price $18995.00") == {18995}
    assert money_amounts("التكلفة ١٨٬٩٩٥ دولار") == {18995}
    assert money_amounts("3 weeks, 24/7 care") == set()
    assert quantities("a 3-week program, Week 1, 24/7 care") == {(3, "week")}
    assert quantities("three weeks or tres semanas or ٣ أسابيع") == {(3, "week")}
    assert quantities("success rate of 85% and 40 percent") == {(85, "%"), (40, "%")}
    assert unsupported_facts("It costs $50", ["Total Cost (USD) | $18,995"]) == ["$50"]
    assert unsupported_facts("It costs $18,995 for 3 weeks", ["$18995 | 3 Weeks"]) == []
    assert unsupported_facts("An 85% success rate over 2 weeks", ["3-Week program"]) == ["2 week", "85%"]
    assert valid_citations(["P1-C2", "X", "P1-C2"], {"P1-C2"}) == ["P1-C2"]
    print("guards ok")
