"""Deterministic checks on LLM answers: money amounts and citations."""
import re

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NUM = r"\d[\d.,\s ٬٫]*\d|\d"
_CURRENCY = r"(?:US\$|USD|\$|dollars?|dólares|dolares|دولار)"
_MONEY = re.compile(rf"(?:{_CURRENCY}\s?(?P<a>{_NUM}))|(?:(?P<b>{_NUM})\s?{_CURRENCY})", re.IGNORECASE)


def _to_int(raw: str) -> int | None:
    digits = re.sub(r"[\s ]", "", raw)
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


def unsupported_amounts(answer: str, evidence: list[str]) -> set[int]:
    """Amounts in the answer that appear nowhere in the evidence texts."""
    allowed = set().union(*(money_amounts(e) for e in evidence)) if evidence else set()
    return money_amounts(answer) - allowed


def valid_citations(cited: list[str], retrieved_ids: set[str]) -> list[str]:
    return [c for c in dict.fromkeys(cited) if c in retrieved_ids]


if __name__ == "__main__":
    assert money_amounts("Out-Patient $18,995 and In-Patient $30,000") == {18995, 30000}
    assert money_amounts("cuesta 18.995 USD") == {18995}
    assert money_amounts("price $18995.00") == {18995}
    assert money_amounts("التكلفة ١٨٬٩٩٥ دولار") == {18995}
    assert money_amounts("3 weeks, 24/7 care") == set()
    assert unsupported_amounts("It costs $50", ["Total Cost (USD) | $18,995"]) == {50}
    assert unsupported_amounts("It costs $18,995", ["$18995"]) == set()
    assert valid_citations(["P1-C2", "X", "P1-C2"], {"P1-C2"}) == ["P1-C2"]
    print("guards ok")
