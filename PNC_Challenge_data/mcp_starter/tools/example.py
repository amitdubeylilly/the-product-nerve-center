"""
Example tool implementation — get_current_date
================================================
This is a reference implementation showing the pattern for tool functions.
Your actual tools will follow the same structure but with real logic.
"""

from datetime import datetime


def get_current_date_impl(format: str = "iso") -> str:
    """
    Return the current date/time in the requested format.

    Args:
        format: "iso" for ISO 8601, "human" for a readable string.

    Returns:
        Formatted date string.

    Raises:
        ValueError: If format is not "iso" or "human".
    """
    now = datetime.now()

    if format == "iso":
        return now.isoformat()
    elif format == "human":
        return now.strftime("%A, %B %d, %Y at %I:%M %p")
    else:
        raise ValueError(
            f"Unknown format '{format}'. Use 'iso' or 'human'."
        )
