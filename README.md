# rn-store-compliance

Claude skills that audit a **React Native / Expo** codebase against both mobile store rulebooks:

- **`rn-ios-review`** — Apple's App Store Review Guidelines, sections 1–5
- **`rn-android-review`** — Google Play's Developer Program Policies plus the Play Console gates that block an upload

Two skills rather than one, so Claude loads only what the task needs — and because the two stores fail differently. Both have upload gates that never reach a human (Apple: build SDK version, age-rating questionnaire; Google: target API level, Billing Library version, AAB format, 16 KB alignment), but Apple's review is a written citation from a person while Google's enforcement often lands *after* publication with account-level consequences. Different checks, different timelines, different people fixing them.

Inspired by [safaiyeh/app-store-review-skill](https://github.com/safaiyeh/app-store-review-skill), rebuilt RN-first: the rule files lead with the TypeScript and manifest patterns that trip each rule, not Swift or Kotlin.

## What this checks, and what it doesn't

**Store compliance first.** Apple's App Store Review Guidelines sections 1–5, Google Play's
Developer Program Policies, and the Play Console / App Store Connect gates that fail an upload
before a human ever sees the build.

Measured across a 34-project fleet, findings break down roughly as: **56% store policy**
(UGC moderation, IAP, purpose strings, ATT, privacy manifests, account deletion, Data safety),
**16% upload gates** (target API, AGP, 64-bit, `UIWebView`, deployment target — these are 110
of 152 BLOCKERs), and **28% security** (hardcoded secrets, cleartext traffic, insecure storage).

Most of that security slice *is* store policy — Apple cites 1.6 and 2.5 for leaked credentials,
Google cites Device & Network Abuse for cleartext. Two checks are the exception:
`SIGNING-SECRET-COMMITTED` and `KEYSTORE-COMMITTED` are not store rules, and neither store will
reject you for them. They are included because a pre-submission audit reliably surfaces this
exposure and staying quiet about it helps nobody.

**This is not a security scanner.** No dependency CVE scanning, no SAST, no taint or data-flow
analysis, no runtime or network testing.

**The scanners are the small half.** They are grep-based lead generators. The rule files are
where the audit actually happens — whether moderation exists in practice, whether the Data safety
form matches the code, whether receipt validation is genuinely server-side. No static check
answers those.

## Requirements

| | |
|---|---|
| Scanners | Python 3.8+, standard library only — no pip install, no network |
| Plugin | Claude Code with plugin support (`/plugin marketplace add`) |
| Skills only | Any Claude surface that reads `SKILL.md` — Claude Code, Claude.ai, Claude Desktop |
| Project | React Native or Expo, managed or bare. Nothing needs to be built, though the Android scanner reads more when it is |

Nothing leaves your machine. The scanners are read-only, make no network calls, and write nothing to the project — safe to run on proprietary or client code. Claude itself will read your files to do the audit, as it would for any task.

## Install

### Claude Code — as a plugin

```bash
/plugin marketplace add <you>/rn-store-compliance
/plugin install rn-store-compliance@bitsol-mobile
```

Local, from a clone:

```bash
cd rn-store-compliance && claude
/plugin marketplace add .
/plugin install rn-store-compliance@bitsol-mobile
```

Test without installing:

```bash
claude --plugin-dir /path/to/rn-store-compliance
```

### Claude Code — skills only

```bash
cp -r skills/rn-ios-review skills/rn-android-review ~/.claude/skills/
```

### Claude.ai / Claude Desktop

Upload `rn-ios-review.skill` and `rn-android-review.skill` and click **Save skill** on each.

## Commands

| Command | Does |
|---|---|
| `/review-ios [path]` | Apple audit only |
| `/review-android [path]` | Play audit only |
| `/review-stores [path]` | Both, with an explicit divergences section |

Or just describe the task — each skill's description triggers it:

```
"Review this React Native app for App Store compliance"
"Will Play reject this upload?"
"Audit both stores before we submit"
"Check our IAP implementation — we ship to iOS and Android"
"We're a HIPAA healthcare app — full pre-submission review"
```

## Scanners

Two, one per platform. Python 3.8+, stdlib only, read-only, no install.

```bash
python3 skills/rn-ios-review/scripts/scan.py /path/to/project
python3 skills/rn-android-review/scripts/scan.py /path/to/project --format json
```

**iOS** (skips `android/`): hardcoded secrets, dynamic code execution, external payment paths, insecure token storage, client-trusted entitlements, tracking SDKs with no ATT call, missing `NSUserTrackingUsageDescription`, missing `PrivacyInfo.xcprivacy`, vague or empty purpose strings, undeclared background modes, IAP without restore, accounts without deletion, UGC without moderation, social login without a 4.8 alternative, custom rating prompts, `NSAllowsArbitraryLoads`, Android references in copy.

**Android** (skips `ios/`): `targetSdkVersion` against Play's floor, Play Billing Library version, APK-instead-of-AAB in CI, native `.so` files needing 16 KB alignment, restricted manifest permissions with the reason each is restricted, missing `foregroundServiceType`, cleartext traffic, `allowBackup`, purchase acknowledgement, accounts without deletion, UGC without moderation, and a Data safety SDK inventory to check the form against.

Both exit 0 — they report, they don't gate. To fail a build:

```bash
python3 scripts/scan.py . --format json | jq -e '[.findings[] | select(.severity=="BLOCKER")] | length == 0'
```

The Android scanner reads the **source** manifest. The one that ships is the **merged** manifest, and the gap between them is where transitive permissions hide — build the app and re-check `android/**/merged_manifests/**/AndroidManifest.xml`. The scanner flags this itself when it doesn't find one.

Both are lead generators. Structural problems — moderation that exists on paper only, a Data safety form that contradicts the code, receipt validation that isn't really server-side — need the rule files and human judgment.

## Bare RN (CLI) vs managed Expo

Both are supported, and the scanners adapt. A bare project checks `ios/` and `android/` into the repo, so more is verifiable:

| | Bare RN (CLI) | Managed Expo |
|---|---|---|
| `Info.plist` purpose strings | read directly | read from `app.json`; verify after `expo prebuild` |
| Privacy manifest | HIGH if missing from `ios/` | MEDIUM "unverified" — generated at prebuild |
| Third-party pods | enumerated from `Podfile.lock` for manifest review | not visible in source |
| Entitlements | flagged for justification | generated by config plugins |
| `ndkVersion`, signing config | checked | not exposed |

If most of your projects are CLI, that's the better-covered path — six checks apply only there.

## Example output

```
$ python3 skills/rn-android-review/scripts/scan.py ./my-app

# Play policy scan — /Users/me/my-app

| Severity | Count |
|---|---|
| BLOCKER | 2 |
| HIGH | 3 |
| MEDIUM | 4 |
| LOW | 1 |

## BLOCKER

- **TARGET-SDK** `android/**/build.gradle` — targetSdkVersion is 34. New uploads
  and updates need API 36+ (enforced 31 Aug 2026); existing apps need at least
  API 35 to stay discoverable. Raising it also makes edge-to-edge mandatory and
  stops onBackPressed firing — budget for that work.
  _Target API level requirement_
  ```
  targetSdkVersion 34
  ```

- **BILLING-VERSION** `android/app/build.gradle` — Play Billing Library 6.x
  detected; the floor moved to 8+ on 31 Aug 2026. The version is pinned by your
  RN billing wrapper — upgrade the package, not gradle.
  _Play Billing Library deprecation_
```

`--format json` gives the same findings as structured data for CI or triage tooling.

Full list of every check both scanners can emit: **[docs/CHECKS.md](docs/CHECKS.md)** — 53 checks, generated from the scanner source so it can't drift.

## Structure

```
rn-store-compliance/
├── .claude-plugin/{plugin.json, marketplace.json}
├── commands/
│   ├── review-ios.md
│   ├── review-android.md
│   └── review-stores.md
├── skills/
│   ├── rn-ios-review/
│   │   ├── SKILL.md
│   │   ├── rules/{1-safety, 2-performance, 3-business, 4-design, 5-legal, health-and-regulated}.md
│   │   ├── references/{rn-package-map, report-template}.md
│   │   └── scripts/scan.py
│   └── rn-android-review/
│       ├── SKILL.md
│       ├── rules/{1-restricted-content, 2-privacy-data, 3-monetization, 4-technical-quality, health-and-regulated}.md
│       ├── references/{rn-package-map, report-template, ios-android-divergences}.md
│       └── scripts/scan.py
├── docs/
│   └── CHECKS.md                 # all 53 checks, generated from source
├── scripts/
│   ├── gen_checks.py             # regenerates docs/CHECKS.md
│   └── prepare_release.py        # fills the <you> placeholders
├── tests/
│   └── test_scanners.py          # 58 tests
├── .github/workflows/test.yml
├── CHANGELOG.md
├── README.md
└── LICENSE
```

## Where the stores disagree

`skills/rn-android-review/references/ios-android-divergences.md` covers this in full. The short version, because it's the thing RN teams get wrong:

- **Payments.** Apple requires StoreKit with narrow entitlement exceptions. Google permits alternative and user-choice billing in several jurisdictions. Your `Platform.OS` branches are *supposed* to differ — don't consolidate them.
- **Data disclosure.** One SDK inventory has to produce three consistent declarations: App Privacy, `PrivacyInfo.xcprivacy`, and the Data safety form. Mismatch between them is itself a violation on both sides, and it's the most common dual-store finding because the forms get filled out months apart.
- **Account deletion.** Apple wants in-app. Google wants in-app *and* a public web URL. Build the web endpoint; it satisfies both.
- **Version floors.** Both stores have one, and they differ in kind: Apple pins the **SDK you build with** (iOS 26 SDK since 28 Apr 2026), Google pins the **API level you target** (36 since 31 Aug 2026). A project can satisfy one and fail the other, months after the last successful upload, with no code change.

## Validation

### v3.0.0 — a fleet of 34 bare RN (CLI) projects

The scanners were audited against a real portfolio of 34 React Native projects,
32 of them bare CLI (`react-native init`, hand-maintained `ios/` and `android/`)
spanning RN 0.35 to 0.84. That is the case this tool is for, and it is where the
previous versions were weakest.

Two findings drove the 3.0.0 rewrite:

- **The noise was fleet-wide.** `SECRET-HARDCODED` fired BLOCKER on every
  project's Firebase config files, which ship by design. `CLEARTEXT` fired HIGH
  on 20 projects' debug-only manifests, which never reach Play. On one
  modern, carefully built health app, **32 of 33 BLOCKER/HIGH findings were
  false** — including `CRASH-PII` firing on the exact code that was tokenising
  health data before logging it.
- **The worst project produced the tamest report.** The oldest app in the fleet
  (RN 0.49) is 32-bit only, on an AGP that predates App Bundles, and vendors
  `UIWebView` — three independent hard upload rejections, none of which the
  scanners could see.

After the fixes, measured on the same projects:

| Project | Before (BLOCKER/HIGH) | After | Notes |
|---|---|---|---|
| Modern health app, RN 0.84 | 33, of which 32 false | **6, all verified real** | Surfaced an empty `NSPrivacyCollectedDataTypes` on an app that POSTs health records, plus a committed release keystore |
| RN 0.76, ships to both stores | 7 | 10 | Added a real `APK-NOT-AAB` and a deployment target inconsistent with its own pod floor |
| RN 0.49, unmaintained | 9, mostly noise | 14 | Added `UIWEBVIEW`, `ABI-NO-64BIT`, `AGP-TOO-OLD` — each one blocks the upload outright |

The point of the "after" numbers is not that they are lower. On two of three
projects they are higher. The point is that they are **true**: a scanner that
flags everything gets ignored, and everything it then misses ships.

### v2.1.0 — bluesky-social/social-app

Earlier versions were validated against
[bluesky-social/social-app](https://github.com/bluesky-social/social-app), which
produced 5 false HIGH findings on compliant code (`@braintree/sanitize-url` read
as a payment SDK, the English word "adjust" read as the analytics SDK, `rate us`
matched inside "sepa**rate us**er"). Each is pinned by a regression test and the
result was 0 BLOCKER / 0 HIGH on both platforms.

**That figure has not been re-measured since 3.0.0 added seven checks**, so
treat it as historical rather than current.

### Caveats

Three projects were verified finding-by-finding; the other 31 informed the
false-positive analysis but were not individually audited. Expect some noise
remaining — `ABI-NO-64BIT` is the likeliest, since a deliberate architecture
trim will trip it. If you get a false positive, open an issue with the matched
line; that is the fastest way to improve this.

## Tests

```bash
python3 tests/test_scanners.py
```

58 tests, stdlib only, no install:

- **Detection** — a deliberately non-compliant fixture asserts each rule fires
- **False positives** — a plausible compliant fixture asserts no BLOCKER or HIGH fires
- **Regressions** — the five real-world false positives above, pinned individually
- **Contract** — JSON shape, markdown rendering, exit codes, empty-project handling

CI runs them on Python 3.8 and 3.12, validates both manifests, and fails the build if an unreplaced `<you>` placeholder is still present.

## Release checklist

Before publishing this as your own marketplace:

- [ ] Fill the placeholders — one command:
  ```bash
  python3 scripts/prepare_release.py --org my-github-org --author "My Name"
  ```
  Add `--dry-run` to preview, `--marketplace my-skills` to rename what users type after `@`. CI fails while any `<you>` remains.
- [ ] Confirm `author` in `plugin.json` and the `LICENSE` copyright holder — `--author` above sets both.
- [ ] Decide on the marketplace name — `bitsol-mobile` is what users type after `@`. It appears in `marketplace.json` and three README commands.
- [ ] Run both scanners against two or three of your own RN repos and check the noise level before anyone else installs it.
- [ ] `python3 tests/test_scanners.py` and `python3 scripts/gen_checks.py --check` both green.

## Troubleshooting

**The skill doesn't trigger.** Each skill fires on its `description` frontmatter. Name the store explicitly — "audit this for App Store review" rather than "check my app" — or use `/review-ios`, `/review-android`, `/review-stores`.

**Scanner reports zero findings.** Check you pointed it at the project root (the directory with `package.json`), not `src/`. On an empty or non-RN directory it exits 0 with nothing found.

**Too many findings on a real repo.** Start with BLOCKER and HIGH; MEDIUM is reviewer discretion and LOW is polish. If a BLOCKER or HIGH is plainly wrong, that's a bug — see Contributing.

**Android permissions look incomplete.** The scanner reads the *source* manifest. The one that ships is the merged manifest, which includes permissions your dependencies add. Build the app, then check `android/**/merged_manifests/**/AndroidManifest.xml`. The scanner emits `MERGED-MANIFEST-NOT-CHECKED` when it can't find one.

**A version floor looks out of date.** Play's floors move every August. They're named constants at the top of the Android `scan.py` (`TARGET_SDK_NEW_UPLOAD`, `BILLING_MAJOR_FLOOR`) — one place to bump.

## Uninstall

```bash
/plugin uninstall rn-store-compliance@bitsol-mobile
/plugin marketplace remove bitsol-mobile
```

Skills copied by hand: delete them from `~/.claude/skills/` or `.claude/skills/`.

## Versioning

Semantic versioning. A **major** bump means a rule's severity changed or a check was removed — things that could change whether your CI gate passes. **Minor** adds checks or rule coverage. **Patch** is false-positive fixes and doc corrections.

Store rules change on their own schedule, so `CHANGELOG.md` separates *what changed in this plugin* from *what changed at Apple or Google*.

## Contributing

The highest-value contribution is a false positive from a real codebase: the matched line, the rule ID, and why it's wrong. Every regression test in `tests/test_scanners.py` started as one of those.

New rules need three things: the guideline or policy it maps to, a detection pattern that matches package names rather than substrings, and a test on both fixtures (fires on dirty, silent on clean).

## Accuracy note

Apple revised the guidelines twice in 2026 (6 February and 8 June); Play's version floors advance every August. Rule files state what was accurate as of the date in each `SKILL.md` frontmatter, and both skills instruct Claude to verify any rule number, API level, or library version against the live page before calling it a blocker. The Android scanner's floors live in named constants at the top of `scan.py` — one place to bump each August.

**What was verified when.** The iOS rule files were checked against Apple Developer news in September 2026, including the February and June 2026 guideline revisions and the age-assurance requirements. The Android rule files had their target API level, Play Billing floor and 16 KB requirement verified at the same time; the remaining Play policy text (Data safety, CSAE, families, restricted permissions) was not independently re-verified against the live policy center and should be treated as a strong prior, not a citation. Re-check before relying on any single Play policy statement in an audit you hand to a client.

MIT.
