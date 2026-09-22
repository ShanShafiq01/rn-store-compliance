"""Assert the scanners import nothing outside the standard library.

Version-proof: rather than comparing against a name list that differs across
Python versions, import each module and check where it actually came from.
Anything resolving into site-packages is a third-party dependency.
"""
import ast, importlib, sys

BAD = ("site-packages", "dist-packages")
failed = False
for f in ("skills/rn-ios-review/scripts/scan.py",
          "skills/rn-android-review/scripts/scan.py"):
    mods = set()
    for node in ast.walk(ast.parse(open(f).read())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    for m in sorted(mods):
        try:
            origin = getattr(importlib.import_module(m), "__file__", "") or ""
        except ImportError:
            print(f"FAIL {f}: cannot import {m}")
            failed = True
            continue
        if any(b in origin for b in BAD):
            print(f"FAIL {f}: {m} resolves to {origin}")
            failed = True
    print(f"ok {f}: {', '.join(sorted(mods))}")
sys.exit(1 if failed else 0)
