"""Split multi-artist credit strings into component artist names."""

import re

SEPARATOR = re.compile(
    r"\s*(?:,|&| x | X | vs\.? | with | feat\.? | ft\.? )\s*",
    re.IGNORECASE,
)


def split_artist_name(name: str) -> list[str]:
    """Return the component artists in a credit string.

    A name with no separator comes back as a single-element list, so callers
    can treat every artist uniformly.
    """
    parts = [p.strip() for p in SEPARATOR.split(name) if p.strip()]
    return parts if len(parts) > 1 else [name]
