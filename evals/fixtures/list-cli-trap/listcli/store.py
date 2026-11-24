import json


def load_entries(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["entries"]


def filter_entries(entries, tag=None):
    if tag is None:
        return list(entries)
    return [e for e in entries if tag in e["tags"]]
