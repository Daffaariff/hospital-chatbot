"""PlacidWay page layout: what to strip and which containers hold facts. Edit here when the site changes."""

NOISE = [
    "script", "style", "noscript", "iframe", "form", "header", "nav", "footer", "aside", "svg", "button",
    "#sidebar", "#cookie-container", "#chatbot-widget", "#alice-chatbot", "article.panel",
    "#cta-form", "[id$='_popup']", ".splide", ".exp-card", ".title-price-row", ".rel-card-title",
    "#reviews", "#testimonials", "#booking", "#location", "#map", ".logos-widget-sec",
]

# NOTE: per page type: which containers hold the facts, and which headings start sections we drop
PAGE_RULES = {
    "clinic_profile": {"keep": ["#about", "#details", "#treatments", "#qualifications", "#awards", "#destination"],
                       "drop_headings": ["Request a Consultation", "Discuss Your Cancer Treatment", "Get More Information"]},
    "package": {"keep": ["#about"], "drop_headings": ["Take the First Step", "Related Experiences"]},
    "price_list": {"keep": ["#prices", "#about"], "drop_headings": ["Reviews"]},
    "price_comparison": {"keep": ["main.search-pricing_page"],
                         "drop_headings": ["What Do Real Families Say", "Ready to Explore", "Quick Facts"]},
}

# --- chunk metadata -------------------------------------------------------------------------------------------
# Topic of each source page, matched on a URL fragment
PAGE_TOPICS = {
    "/package/7903/": "adenocarcinoma",
    "/package/7902/": "adrenal",
    "/package/7901/": "anal",
    "/profile/5/": "itc",
    "/price-list/5/": "itc",
    "/profile-videos/5/": "videos",
    "/search-medical-pricings/": "alt_medicine",
}

# Section type from the heading, first match wins (lower-cased substring)
SECTION_TYPES = [
    ("excluded", "excluded"), ("not included", "excluded"),
    ("included in", "included"), ("typically included", "included"),
    ("optional", "optional"),
    ("itinerary", "itinerary"),
    ("which clinics", "clinic_prices"),
    ("cost of", "cost"), ("pricings", "cost"), ("cost and packages", "cost"), ("how much does", "cost"),
    ("overview", "cost"), ("cost breakdown", "cost"),
]

COUNTRIES = ["Mexico", "Turkey", "Thailand", "India", "Costa Rica", "Colombia", "Germany", "Spain"]

# --- query vocabulary (applied to the router's English query) ---------------------------------------------------
TREATMENT_TERMS = {
    "adenocarcinoma": "adenocarcinoma",
    "adrenal": "adrenal",
    "anal": "anal", "anus": "anal", "colostomy": "anal",
    "breast": "itc", "lung": "itc", "prostate": "itc", "pancreatic": "itc", "colon": "itc", "colorectal": "itc",
    "ozone": "alt_medicine", "acupuncture": "alt_medicine", "ayurvedic": "alt_medicine", "naturopathic": "alt_medicine",
    "abroad": "alt_medicine",
}

# Phrase -> section type, checked in order (so "not included" wins over "included")
SECTION_TERMS = [
    ("not included", "excluded"), ("not covered", "excluded"), ("excluded", "excluded"), ("extra cost", "excluded"),
    ("additional cost", "excluded"), ("hidden cost", "excluded"),
    ("optional", "optional"),
    ("included", "included"), ("include", "included"), ("what do i get", "included"),
    ("itinerary", "itinerary"), ("week 1", "itinerary"), ("week 2", "itinerary"), ("week 3", "itinerary"),
    ("schedule", "itinerary"),
    ("clinic", "clinic_prices"), ("turkey", "clinic_prices"), ("thailand", "clinic_prices"),
    ("istanbul", "clinic_prices"),
    ("price", "cost"), ("cost", "cost"), ("how much", "cost"), ("charge", "cost"), ("cheap", "cost"),
    ("expensive", "cost"), ("fee", "cost"),
]
