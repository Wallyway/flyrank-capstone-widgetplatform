import re

from fastapi import HTTPException

from app import config

# Not RFC 5322. It rejects the obviously-not-an-address cases without pretending
# that a regex can decide whether a mailbox exists.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")

TRUTHY = {"true", "on", "yes", "1"}
FALSY = {"false", "off", "no", "0", ""}


def validate_submission(widget: dict, data) -> dict:
    """Check a visitor's payload against the field list its widget declares.

    The widget's own config is the schema. Anything not declared is refused
    rather than stored, so a widget can never be used as a free JSON bucket.
    """
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="data: must be an object")

    declared = {field["name"]: field for field in widget["fields"]}
    errors = []

    for name in data:
        if name not in declared:
            errors.append(f"{name}: unknown field for this widget")

    cleaned = {}
    for name, field in declared.items():
        value = data.get(name)
        missing = value is None or (isinstance(value, str) and not value.strip())

        if missing:
            if field.get("required"):
                errors.append(f"{name}: required")
            continue

        problem, value = coerce(field, value)
        if problem:
            errors.append(f"{name}: {problem}")
            continue
        cleaned[name] = value

    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return cleaned


def coerce(field: dict, value):
    """Return (error message or None, converted value)."""
    kind = field["type"]

    if kind == "checkbox":
        if isinstance(value, bool):
            return None, value
        text = str(value).strip().lower()
        if text in TRUTHY:
            return None, True
        if text in FALSY:
            return None, False
        return "must be true or false", None

    if kind == "number":
        try:
            return None, float(value)
        except (TypeError, ValueError):
            return "must be a number", None

    if not isinstance(value, (str, int, float)):
        return "must be text", None
    text = str(value).strip()

    # Two limits: what the widget asked for, and the platform ceiling. The
    # smaller one wins, so a widget cannot raise its own limit.
    limit = min(field.get("max_length") or config.MAX_FIELD_LENGTH, config.MAX_FIELD_LENGTH)
    if len(text) > limit:
        return f"must be at most {limit} characters", None

    if kind == "email" and not EMAIL_PATTERN.match(text):
        return "not a valid email address", None

    if kind == "select":
        options = field.get("options") or []
        if text not in options:
            return f"must be one of {options}", None

    return None, text
