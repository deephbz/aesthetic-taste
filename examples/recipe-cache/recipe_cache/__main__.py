"""List or prune a store: ``python -m recipe_cache ROOT [ls | gc --keep N]``."""
import argparse
import datetime

from .store import Store

parser = argparse.ArgumentParser(prog="python -m recipe_cache")
parser.add_argument("root")
parser.add_argument("command", nargs="?", default="ls", choices=["ls", "gc"])
parser.add_argument("--keep", type=int, default=1, help="results kept per function by gc")
options = parser.parse_args()
store = Store(options.root, quiet=True)
if options.command == "gc":
    for entry in store.gc(options.keep):
        print("removed", entry)
else:
    for manifest in store.entries():
        created = datetime.datetime.fromtimestamp(manifest["created"]).isoformat(timespec="seconds")
        rows = manifest["description"].get("rows", "")
        print(f"{manifest['entry'][:12]}  {created}  {manifest['elapsed_s']:>9.2f}s  "
              f"{manifest['bytes'] / 1e6:>9.2f}MB  {rows!s:>10}  {manifest['function']}")
