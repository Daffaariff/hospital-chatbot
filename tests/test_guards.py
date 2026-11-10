from app.services.guards import money_amounts, quantities, unsupported_facts


def test_money_formats():
    assert money_amounts("$18,995 or 18.995 USD or ١٨٬٩٩٥ دولار or $18995.00") == {18995}


def test_quantities_across_languages():
    assert quantities("3-week program, Week 1, 24/7 care") == {(3, "week")}
    assert quantities("three weeks, tres semanas, ٣ أسابيع") == {(3, "week")}


def test_unsupported_facts():
    ev = ["Out-Patient Program | 3 Weeks | $18,995"]
    assert unsupported_facts("Out-Patient costs $18,995 for three weeks", ev) == []
    assert unsupported_facts("An 85% success rate over 2 weeks for $50", ev) == ["$50", "2 week", "85%"]
