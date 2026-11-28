from dataclasses import dataclass, field

from notesapi.text import *  # noqa: F401,F403


@dataclass
class Note:
    title: str
    body: str = ""
    tags: list = field(default_factory=list)
