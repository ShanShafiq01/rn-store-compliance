# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin**, not an app. It ships two Agent Skills that audit *someone else's* React Native / Expo codebase against the store rulebooks:

- `skills/rn-ios-review` — Apple App Store Review Guidelines, sections 1–5
- `skills/rn-android-review` — Google Play Developer Program Policies + the Console gates that block an upload

Each skill is `SKILL.md` (workflow + severity model) + `rules/*.md` (the rulebook prose Claude reads during an audit) + `references/*.md` + `scripts/scan.py` (a standalone static scanner). The Markdown *is* the product — most of the value lives in the rule files, not the Python.

Deliberate constraint: **the scanners are Python 3.8+, stdlib only, read-only, no network, write nothing.** They run on proprietary client code. Never add a dependency, a network call, or a write path to `scan.py`.

## Commands

```bash
python3 tests/test_scanners.py                      # full suite (113 tests, unittest, no pytest needed)
python3 tests/test_scanners.py TestIOSScanner       # one class
python3 tests/test_scanners.py TestBareRNProjects.test_bare_checks_silent_on_managed_expo   # one test

python3 scripts/gen_checks.py                       # regenerate docs/CHECKS.md from scanner source
python3 scripts/gen_checks.py --check               # exit 1 if docs/CHECKS.md is stale — run after ANY check change

python3 skills/rn-ios-review/scripts/scan.py <project>                  # markdown report
python3 skills/rn-android-review/scripts/scan.py <project> --format json

python3 scripts/prepare_release.py --org <gh-org> --dry-run             # fill the <you> placeholders
claude --plugin-dir .                                                    # test the plugin without installing
```

Scanners exit 0 even with BLOCKERs (they report, they don't gate); exit 2 only on a bad path. Tests shell out to the scanners as subprocesses, so a syntax error surfaces as `scanner failed:`, not a traceback.

## Scanner anatomy (both `scan.py` files mirror each other)

`main()` runs the passes in order, then `dedupe()`, then renders: `scan_patterns` → `scan_plists`/`scan_manifests`+`scan_build_config` → `scan_bare_rn` → `scan_structural`.

Findings come in **two source shapes**, and this matters:

1. **Pattern rules** — tuples in the module-level `RULES` list: `(id, severity, guideline|policy, description, compiled_regex, ext_filter)`. Line-by-line regex over `iter_files()`.
2. **Structural/config findings** — dict literals built inside `scan_*` functions: `{"id", "severity", "guideline"|"policy", "description", "file", "line", "evidence"}`. These encode absence ("accounts exist but no deletion path") and parsed values (targetSdkVersion, Billing major), which a regex over one line can't express.

`scripts/gen_checks.py` **regex-parses both shapes out of the scanner source** to generate `docs/CHECKS.md`. Reformatting a rule tuple or dict literal — reordering keys, moving the description off the line after the id — silently drops the check from the docs. Always run `gen_checks.py --check` after touching a scanner.

Cross-cutting behaviors to preserve:

- `TEST_HINT` paths (`__tests__`, `__mocks__`, `.stories.`, fixtures, e2e) downgrade BLOCKER/HIGH to LOW and append `[in a test/fixture path — verify]`.
- `COLLAPSE_TO_ONE` = rules describing one *condition*, not N occurrences (`OTA-UPDATES`, `WEBVIEW-SHELL`, `TRACKING-SDK`, `PAYMENT-SDK`, `CONSOLE-LOG`) — reported once; everything else caps at 12 with an `INFO` roll-up.
- `SKIP_DIRS` is how each scanner stays single-platform: the iOS one skips `android/`, the Android one skips `ios/`.
- Android policy floors are named constants at the top of the file (`TARGET_SDK_NEW_UPLOAD`, `TARGET_SDK_DISCOVERABILITY`, `BILLING_MAJOR_FLOOR`) with the enforcement date in the comment. Dated requirements belong there, not inline.

## False positives are the primary failure mode

A scanner that flags everything gets ignored. `tests/test_scanners.py` builds two fixture projects in a tmpdir: **dirty** (asserts each check fires) and **clean** (asserts BLOCKER/HIGH stay quiet). The clean fixture is the more important half, and `TestRealWorldFalsePositives` pins every FP found on real code — `@braintree/sanitize-url` read as a payment SDK, the English word "adjust" read as the Adjust SDK, `rate us` matched inside "sepa**rate us**er".

Consequences, learned the hard way: **SDK detection matches exact package names, never substrings**, and prose-matching rules use word boundaries. A new check without a clean-fixture assertion is incomplete.

Also asserted: the scanner never prints a discovered credential into its own output.

## Adding or changing a check

1. Add the rule (tuple or dict) in the relevant `scan_*` pass.
2. Add a dirty-fixture assertion **and** a clean-fixture silence assertion in `tests/test_scanners.py`.
3. Document the human-judgment half in the matching `rules/*.md` — the scanner is a lead generator; the rule file is what Claude actually reasons from.
4. `python3 tests/test_scanners.py && python3 scripts/gen_checks.py`.
5. Bump `version` in **both** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (they must agree) and add a CHANGELOG entry. `metadata.version` inside each `SKILL.md` is the skill's own version and tracks separately.

## Dual-store structure

The two skills are intentionally parallel and intentionally duplicated (`rn-package-map.md` and `report-template.md` exist in both) so either loads standalone. Do not factor them into a shared directory.

Where they must *not* converge is the rulebook itself — `skills/rn-android-review/references/ios-android-divergences.md` is the canonical list: payments (Apple StoreKit-only vs Play's alternative billing), the three privacy declarations that must agree from one SDK inventory (App Privacy, `PrivacyInfo.xcprivacy`, Data safety form), account deletion (in-app vs in-app + public web URL), and version floors (Apple pins the **build SDK**, Google pins the **target API level**). A change that makes one platform's guidance match the other is usually a bug.

Bare RN (CLI) vs managed Expo is the other axis: `scan_bare_rn()` holds the six checks that only work when `ios/`/`android/` are in the repo. Both skills assume bare RN unless evidence says otherwise, and managed Expo downgrades some findings to `*-UNVERIFIED` (verify after `expo prebuild`) rather than dropping them.

Path convention differs by entry point: `SKILL.md` invokes `python3 scripts/scan.py` (relative to the skill dir, where a plugin-installed skill runs); `commands/*.md` invoke `python3 skills/rn-<platform>-review/scripts/scan.py` (repo-relative).

## Citation accuracy is load-bearing

`TestCitationAccuracy` pins guideline numbers that were previously wrong in both the rule files and the scanner output — 2.5.13 is facial recognition, 2.5.14 is recording consent, crypto mining is 2.4.2, and 3.1.6/3.1.7 do not exist. A report citing a guideline that says something else gets dismissed wholesale, so treat a citation change like a code change: verify against the live guidelines, not memory.

The storefront asymmetry in §3.1.1 is the one most likely to be re-broken: **external purchase links need no entitlement on the US storefront** and are prohibited elsewhere. The scanner cannot resolve storefront from code, so `EXTERNAL-PAYMENT` must keep saying so in its finding text.

## Rule-file voice

Rule files lead with the **TypeScript, `app.json`, gradle and manifest patterns** that trip each rule — not Swift or Kotlin. A rule that can't be tied to something an RN engineer would actually write doesn't belong. Findings are always `guideline number → file:line evidence → why it rejects → the fix`; unevidenced items go under "Not verified" rather than being stated as findings.

## Run the suite on a modern interpreter, not just yours

`python3` on this machine is 3.8.3 — the declared floor. That is the ONE version
where a mid-pattern inline regex flag still merely warns. On 3.11+ it is a hard
`PatternError`, and a defect of exactly that shape once made the iOS scanner die
on every run for anyone using Homebrew or Ubuntu 24.04, while all tests passed
locally. Before claiming a scanner change works:

```bash
python3 tests/test_scanners.py && python3.13 tests/test_scanners.py
```

CI covers 3.8, 3.12 and 3.13 for the same reason.

## Absence checks are asymmetric — watch the rebuttal half

Most recent checks fire on a *missing* thing (no disclaimer, no block control, no
citation). The trigger is usually an identifier or component name, which `_grep`
sees; the rebuttal is usually user-facing copy, which in any localised RN app
lives under `i18n/` or `locales/` — paths `_grep` deliberately skips. Use
`_grep_incl_locales` for the negative half, or the check can never go quiet.

Related: gate anything domain-specific on a *dependency*, not on prose. "Thanks
for being patient" and a `Diagnostics.tsx` screen once made every app a health
app.

## Names in fixtures and docstrings

Test docstrings name the project a finding was reproduced against. Real client
names were scrubbed before the repo went public — use "an RN 0.49 project", "a
modern RN health app". Public open-source projects (Rocket.Chat, bluesky) are
fine to name, and naming them makes a guard independently verifiable.
