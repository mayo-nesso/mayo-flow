import argparse

from listcli.store import filter_entries, load_entries


def build_parser():
    p = argparse.ArgumentParser(prog="listcli")
    sub = p.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="list entries")
    ls.add_argument("--file", default="data.json")
    ls.add_argument("--tag", help="only entries with this tag")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    entries = filter_entries(load_entries(args.file), tag=args.tag)
    for e in entries:
        print(f"{e['name']}\t{','.join(e['tags'])}")
