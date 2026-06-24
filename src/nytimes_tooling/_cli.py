"""Small shared CLI helpers used by the command entry points."""

from datetime import date


def today_iso() -> str:
    """Today's date as a YYYY-MM-DD string."""
    return date.today().isoformat()


def default_to_today(syntax: str) -> str:
    """
    Announce that no date was given, print the command syntax, and return today.

    Used by every command so a bare invocation does something useful (acts on
    today) while still teaching the caller how to pass an explicit date.
    """
    today = today_iso()
    print(f"No date given - defaulting to today ({today}).")
    print(f"Syntax: {syntax}")
    return today
