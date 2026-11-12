"""Replace this example with project-specific domain behavior."""


def normalize_label(value: str) -> str:
    """Collapse whitespace and reject a label containing no visible characters."""
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("Label must not be empty")
    return normalized
