#!/usr/bin/env python3
"""
Fill the release placeholders in one shot.

The repo ships with `<you>` in the manifests and README because the GitHub
org can't be guessed. CI fails while any remain, so this closes the last
release gate:

    python3 scripts/prepare_release.py --org my-github-org
    python3 scripts/prepare_release.py --org my-org --author "My Name" \\
        --marketplace my-skills --dry-run

--marketplace renames what users type after `@` when installing, in
marketplace.json and every README install command.
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_FILES = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "README.md",
    "LICENSE",
]


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, content):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
        f.write(content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True, help="GitHub org or username that will host the repo")
    ap.add_argument("--repo", default="rn-store-review", help="repository name (default: rn-store-review)")
    ap.add_argument("--author", help="author name for plugin.json and the LICENSE copyright")
    ap.add_argument("--marketplace", help="rename the marketplace (default: leave as-is)")
    ap.add_argument("--dry-run", action="store_true", help="show the changes without writing")
    args = ap.parse_args()

    old_market = json.loads(read(".claude-plugin/marketplace.json"))["name"]
    changes = {}

    for rel in TEXT_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        before = read(rel)
        after = before.replace("<you>", args.org)
        if args.repo != "rn-store-review":
            after = after.replace("rn-store-review", args.repo)
        if args.marketplace:
            after = after.replace(old_market, args.marketplace)
        if args.author:
            after = re.sub(r'"name":\s*"Bitsol Technologies"',
                           f'"name": "{args.author}"', after)
            after = re.sub(r"Copyright \(c\) (\d{4}) .*",
                           rf"Copyright (c) \1 {args.author}", after)
        if after != before:
            changes[rel] = after

    if not changes:
        print("nothing to change — placeholders already filled")
        return 0

    for rel in changes:
        print(f"{'would update' if args.dry_run else 'updated'}: {rel}")
    if args.dry_run:
        return 0

    for rel, content in changes.items():
        write(rel, content)

    remaining = []
    for rel in TEXT_FILES:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path) and "<you>" in read(rel):
            remaining.append(rel)
    if remaining:
        print(f"WARNING: <you> still present in {remaining}", file=sys.stderr)
        return 1

    print("\nDone. Next:")
    print("  python3 tests/test_scanners.py")
    print("  python3 scripts/gen_checks.py --check")
    print("  git add -A && git commit -m 'prepare release'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
