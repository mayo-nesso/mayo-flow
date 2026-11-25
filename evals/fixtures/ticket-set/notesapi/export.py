def export_text(notes):
    """Return one line per note: the title, a colon and the body."""
    return "\n".join(f"{n.title}: {n.body}" for n in notes)
