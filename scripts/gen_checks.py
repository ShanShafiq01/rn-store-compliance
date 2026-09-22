#!/usr/bin/env python3
"""
Generate docs/CHECKS.md from the scanner source.

The check inventory is extracted from scan.py rather than maintained by hand,
so the documented severity of a rule can never drift from the one it emits.
CI runs this with --check and fails if the committed file is stale.

    python3 scripts/gen_checks.py            # write docs/CHECKS.md
    python3 scripts/gen_checks.py --check    # exit 1 if out of date
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "CHECKS.md")
ORDER = {"BLOCKER": 0, "HIGH": 1, "HIGH/MEDIUM": 1, "MEDIUM": 2, "LOW": 3}

SCANNERS = [
    ("iOS", "skills/rn-ios-review/scripts/scan.py", "App Store Review Guidelines"),
    ("Android", "skills/rn-android-review/scripts/scan.py", "Play policy / Console requirement"),
]


def extract(path):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    rows = []

    # Pattern-matching rules: (id, severity, rule_ref, description, regex, exts)
    for m in re.finditer(
        r'\(\s*"([A-Z0-9\-_]+)",\s*"(BLOCKER|HIGH|MEDIUM|LOW)",\s*"([^"]+)",\s*\n\s*"([^"]+)', src
    ):
        rows.append((m.group(1), m.group(2), m.group(3), m.group(4)))

    # Structural and config findings built as dict literals
    for m in re.finditer(
        r'"id":\s*"([A-Z0-9\-_]+)",\s*"severity":\s*"(BLOCKER|HIGH|MEDIUM|LOW)",\s*'
        r'"(?:guideline|policy)":\s*"([^"]*)",\s*\n?\s*"description":\s*"([^"]*)',
        src,
    ):
        rows.append((m.group(1), m.group(2), m.group(3), m.group(4)))

    # Restricted Android permissions
    perms = re.search(r"PERMISSIONS = \{(.*?)\n\}", src, re.S)
    if perms:
        names = re.findall(r'"(\w+)":\s*\("(HIGH|MEDIUM)"', perms.group(1))
        if names:
            listed = ", ".join(f"`{n}`" for n, _ in names[:6])
            rows.append((
                f"PERM-&lt;NAME&gt;", "HIGH/MEDIUM", "Play permissions policy",
                f"{len(names)} restricted or sensitive permissions detected in the manifest, "
                f"each reported with why it is restricted — {listed}, and more",
            ))

    seen, uniq = set(), []
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0])
            uniq.append(r)
    return sorted(uniq, key=lambda r: (ORDER.get(r[1], 9), r[0]))


def render():
    lines = [
        "# Check reference",
        "",
        "Every finding the two scanners can emit. **Generated from the scanner source by "
        "`scripts/gen_checks.py`** — don't edit by hand; CI fails if this file drifts from the code.",
        "",
        "Severity meanings are in each skill's `SKILL.md`. In short: BLOCKER stops the release, "
        "HIGH is a commonly cited rejection or an enforcement risk, MEDIUM is reviewer discretion, "
        "LOW is polish.",
        "",
        "Every check is a **lead, not a verdict**. Confirm each hit by reading the code around it — "
        "and note that a clean scan is not compliance, since the structural problems (moderation "
        "quality, whether a disclosure form matches the code, whether receipt validation really "
        "happens server-side) are not detectable by static analysis.",
        "",
    ]
    total = 0
    for name, path, col in SCANNERS:
        rows = extract(path)
        total += len(rows)
        lines += [
            f"## {name} — {len(rows)} checks",
            "",
            f"`skills/rn-{name.lower()}-review/scripts/scan.py`",
            "",
            f"| ID | Severity | {col} | What it means |",
            "|---|---|---|---|",
        ]
        for rid, sev, ref, desc in rows:
            desc = desc.replace("|", "\\|").strip()
            if len(desc) > 150:
                desc = desc[:147].rsplit(" ", 1)[0] + "…"
            lines.append(f"| `{rid}` | {sev} | {ref} | {desc} |")
        lines.append("")
    lines.insert(3, f"**{total} checks total.**")
    lines.insert(4, "")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if docs/CHECKS.md is stale")
    args = ap.parse_args()

    content = render()
    if args.check:
        if not os.path.exists(OUT):
            print("docs/CHECKS.md missing — run scripts/gen_checks.py", file=sys.stderr)
            return 1
        if open(OUT, encoding="utf-8").read() != content:
            print("docs/CHECKS.md is stale — run scripts/gen_checks.py", file=sys.stderr)
            return 1
        print("docs/CHECKS.md up to date")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(content)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
