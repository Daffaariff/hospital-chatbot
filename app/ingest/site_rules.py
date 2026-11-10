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
