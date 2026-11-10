"""Tolerant JSON extraction for model output."""


def extract_json(text: str) -> str:
    """Keep the outermost {...}, so prose or ``` fences around a JSON object don't break parsing."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text
