"""Shared constants and helpers for action_type normalisation and ID validation."""

import re

# Maps common LLM-generated synonyms to canonical action_types.
# Unknown action_types are preserved as-is (not discarded).
ACTION_TYPE_ALIASES: dict[str, str] = {
    "clicked": "click",
    "tap": "click",
    "press": "click",
    "check": "click",
    "checked": "click",
    "select": "click",
    "long click": "long_click",
    "longclick": "long_click",
    "long_press": "long_click",
    "scroll up": "scroll",
    "scroll down": "scroll",
    "scroll left": "scroll",
    "scroll right": "scroll",
    "scroll_up": "scroll",
    "scroll_down": "scroll",
    "scroll_left": "scroll",
    "scroll_right": "scroll",
    "swipe": "scroll",
    "home activity": "home",
    "go to": "go_to",
    "goto": "go_to",
    "go": "go_to",
    "go_to_activity": "go_to",
    "go_to_next_activity": "go_to",
    "go to next activity": "go_to",
    "goto_activity": "go_to",
    "go_to_next": "go_to",
    "go to next": "go_to",
    "go to activity": "go_to",
    "navigate": "go_to",
    "input": "type",
    "enter": "type",
    "entered": "type",
    "fill": "type",
    "pressed": "click",
    "open navigation drawer": "click",
    "none": "click",
}

# action_types that represent log noise, not real user actions
JUNK_ACTION_TYPES: set[str] = {
    "error",
    "warn",
    "warning",
    "not_found",
    "not found",
    "element_not_found",
    "element not found",
    "exception",
    "failure",
    "timeout",
    "crash",
}

# Regex matching IDs that should be treated as N/A (not real resource IDs)
INVALID_ID_RE: re.Pattern[str] = re.compile(
    r"(^null$|^none$|^N/A$|^nan$|bounds:\[|/null$|/none$|\s)",
    re.IGNORECASE,
)


def normalize_action_type(raw: str) -> str | None:
    """Normalize an action_type value.

    Returns the canonical action_type, or None if it's junk.
    Unknown action_types are preserved as-is.
    """
    clean = raw.strip().lower()
    if clean in JUNK_ACTION_TYPES:
        return None
    return ACTION_TYPE_ALIASES.get(clean, clean)


def normalize_id(raw_id: str) -> str:
    """Normalize a resource ID. Returns 'N/A' for invalid IDs."""
    if not raw_id or INVALID_ID_RE.search(raw_id):
        return "N/A"
    return raw_id
