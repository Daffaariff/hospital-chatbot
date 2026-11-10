"""Fixed values shared across the app (tunable settings live in config.py)."""

# Router intents that get a short reply without retrieval, and those that open the lead form
NO_RETRIEVAL_INTENTS = {"greeting", "booking", "quote_request", "out_of_scope"}
LEAD_INTENTS = {"booking", "quote_request"}
PRICE_INTENTS = {"price", "comparison"}

COLLECTION = "placidway"
CHUNK_MAX_CHARS = 1500
