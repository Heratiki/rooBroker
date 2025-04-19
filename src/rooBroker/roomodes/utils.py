import re


def slugify(name: str) -> str:
    """Create a slug for the mode from the model name."""
    # Lowercase, replace non-alphanum with hyphens, collapse multiple hyphens, strip
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return f"{slug}-mode"
