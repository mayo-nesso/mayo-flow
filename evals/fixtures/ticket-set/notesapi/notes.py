from dataclasses import dataclass, field


@dataclass
class Note:
    title: str
    body: str = ""
    tags: list = field(default_factory=list)


def normalize_title(title):
    """Return the title without outer spaces, in lower case."""
    return title.strip().lower()
