"""Text helpers shared by the package."""


def normalize_title(title):
    """Return the title without outer spaces, in lower case."""
    return title.strip().lower()
