def search_notes(notes, word):
    """Return the notes whose title contains the word (exact case)."""
    return [n for n in notes if word in n.title]
