# Changelog

## [3.2.0] — 2026-09-30

A second rejection round on the same app, plus a coverage audit against the live
Apple guidelines and Play Policy Center. 62 → 84 documented checks.

### Fixed — 14 checks were invisible
`gen_checks.py` builds `docs/CHECKS.md` by reading the scanner source, and its
extractor required a string-literal severity and a non-f-string description. It
silently dropped every check computing either — 14 of them, including
`TARGET-SDK`, `UIWEBVIEW`, `ABI-NO-64BIT`, `AGP-TOO-OLD` and
`KEYSTORE-COMMITTED`. `--check` could not notice, because it compares the
generator's output against the file the generator wrote. A test now asserts
every ID in either scanner appears in `docs/CHECKS.md`.

Also: the 16 KB NDK floor was wrong (r28+ aligns by default; r27 needs explicit
linker flags, and r27 projects were passing while shipping unaligned), and the
iOS `MINING` rule matched bare `hashrate`, which a price tracker displays as
content.

### Added — from the rejection letter
- `UGC-BLOCK-MISSING` (HIGH, 1.2) — Apple credited an app's reporting *and*
  admin moderation and still held the build: 1.2 needs a self-service block.
  The old check went quiet as soon as any moderation path existed.
- `UGC-COMMENT-REPORT-MISSING` (MEDIUM, 1.2) — reporting a post is not
  reporting a comment.
- `HEALTHKIT-PERM-UNUSED` (HIGH, 2.1) — declared Health access must match what
  the app reads. Android had the Health Connect equivalent; iOS did not.
- `FRAMEWORK-UNUSED` (HIGH, 2.1) — *"includes the PassKit framework… unable to
  verify any integration of Apple Pay."*

### Added — Apple coverage
`IAP-UNFINISHED-TRANSACTION` (2.3.2 / 2.1), `SOCIAL-REVOKE-MISSING` (5.1.1(v)),
`AD-REPORT-MISSING` (2.5.18 — the entire iOS advertising rule set was absent),
`HEALTH-DATA-TO-ADS` (5.1.2(vi)), `MEDIA-DOWNLOADER` (5.2.3).

### Added — Play coverage
`PACKAGE-NAME-PLACEHOLDER` (Console Requirements),
`ACCESSIBILITY-AGENTIC-AUTOMATION` (clarified 30 Oct 2025 — agentic use of the
Accessibility API is prohibited; deterministic automation is not),
`MINING` (parity — iOS caught it, Android was blind), `INCENTIVIZED-RATING`,
`STORE-LISTING-TITLE`.

### False positives designed out, not discovered later
Each new check ships with the exclusion that makes it quiet: RevenueCat and
Qonversion finish transactions internally, so `IAP-UNFINISHED-TRANSACTION`
skips them; `react-native-fbsdk-next` is login, not Audience Network, so it is
not an ads trigger; `HEALTH-DATA-TO-ADS` requires the health *value* to reach
the call rather than an ads SDK merely co-existing; rewarded-ad code cannot
trigger `INCENTIVIZED-RATING`; localized `strings.xml` is not read for the
title; and the accessibility check needs a declared *service* plus an LLM, so
a11y props and testing libraries can never match.

### Tests
113 → 138, green on Python 3.8.3 and 3.13.0. Fleet impact across 35 projects:
959 → 973 findings, every new check at or under 3%.

## [3.1.0] — 2026-09-28

Driven by a real App Store rejection letter for a health app. A rejection is the
highest-quality input this tool can get: a reviewer has already decided the rule
applies, so these went in ahead of any speculative coverage. Six of the seven
points were not covered at all.

### Added — checks
- `SIWA-REDUNDANT-PROFILE` (HIGH, 4.8) — Sign in with Apple beside a
  profile-completion screen. Offering the button is not the same as meeting its
  design requirements. The RN trap: `fullName` and `email` come back only on the
  FIRST authorization, so teams add a "complete your profile" screen, which is
  the thing Apple cites.
- `MEDICAL-NO-DISCLAIMER` (HIGH, 1.4.1) — health app with medical language and
  no reminder to consult a doctor. The rejection asked for the App Store
  *description* to be revised, not the app, so the finding says to fix both.
- `MEDICAL-NO-CITATION` (MEDIUM, 1.4.1) — medical claims with no reachable
  source. Citations in a privacy policy do not count.
- `SENSOR-ONLY-VITALS` (BLOCKER, 1.4.1) — quotes the guideline verbatim: apps
  claiming to take x-rays or measure blood pressure, body temperature, blood
  glucose or blood oxygen "using only the sensors on the device are not
  permitted". Deliberately NOT gated on a health SDK: the claim itself is the
  health signal, and gating would exclude the apps the rule aims at.
- `SUBSCRIPTION-COPY-MISMATCH` (MEDIUM, 3.1.1 / 3.1.3(e)) — purchase copy saying
  "subscription" with no IAP library. A real 2.1(b) hold was caused by exactly
  this: one-time program purchases described as subscriptions, so the reviewer
  looked for auto-renewing products and found none.
- `HEALTH-PERM-UNUSED` (HIGH) — Health Connect permissions declared but never
  read. Access is granted per data type against a declared use case, so an
  unused type is an over-request that can cost the whole grant.
- `AI-CONTENT-NO-REPORT` (HIGH) — a model SDK with no in-app reporting path.
  Play requires users to be able to flag offensive AI output without leaving the
  app; a support email does not satisfy it. iOS already covered this under 1.2
  and 4.7; Android had nothing.

### Added — rule prose
- Guideline 2.1 review-notes guidance for apps that ingest documents or run a
  model, from a real 2.1 hold that asked for a sample lab result, the upload
  pipeline, and a list of every AI-produced output. None of that is visible in a
  build, so review never finds it — the reviewer asks, and that costs a cycle.
  Also records the built-in demo mode alternative, which needs Apple's approval
  before submission.
- Play's AI-Generated Content policy, including the Console self-declaration for
  AI-generated store listing assets and the 15 Jul 2026 clarification that the
  User Data policy covers third-party AI integrations.
- Health Connect per-type approval, and the 5 Mar 2025 health-records tightening.

### Fixed
- **3.1.3(e), not 3.1.5(a)**, is Goods and Services Outside of the App. 3.1.5 is
  Cryptocurrencies. The stale number appears in circulating rejection-response
  templates; quoting it invites a second review round.

### Fixed — false positives, found by scanning 34 projects
- `SUBSCRIPTION-COPY-MISMATCH` matched Rocket.Chat's room-subscription data
  model (`subscriptions.get`), and would have matched GraphQL and RxJS
  subscriptions. Now requires billing context on the same line: 9 projects → 2.
- `AI-CONTENT-NO-REPORT` matched the English word "replicate" in medical prose
  about bacteria replicating inside immune cells. Now matches package names
  only — the same discipline the "adjust" bug taught in 2.1.0.

### Divergence recorded
Play bars using sensitive health data for employment or insurance eligibility;
Apple 5.1.3 permits health data to deliver a benefit such as a reduced insurance
premium when the benefit provider submits the app. One feature, opposite
verdicts.

### Tests
69 → 89. Fleet impact: 949 → 964 findings across 35 projects, i.e. 15 net new,
all inspected.

## [3.0.0] — 2026-09-22

Audited against a fleet of 34 real bare React Native (CLI) projects rather than
fixtures. That surfaced three classes of problem: checks that could never fire,
findings that fired on everything, and guideline citations that were simply
wrong. Major version because severities, citations and check IDs all changed —
anything gating CI on this output will see different results.

### Fixed — checks that existed but were structurally dead
- `ARBITRARY-LOADS` was matched per line while plists split `<key>` and `<true/>`
  across two lines. A HIGH 1.6 check that fired on **zero** real projects.
- The signing-credential regex required `=` or `:`; Groovy's gradle DSL is
  space-separated, so every genuinely committed password was missed. Now reports
  each occurrence at its true line rather than only the first.
- The CI path list omitted `android/fastlane/Fastfile`, where RN projects
  actually keep it, so the `APK-NOT-AAB` BLOCKER fired on nothing. Fastlane's
  `gradle(task: "assemble")` form is recognised alongside `assembleRelease`.
- Merged manifests live under `build/`, which `SKIP_DIRS` prunes, so the
  advisory that `SKILL.md` and both rule files are built around was unreachable
  by construction.
- `TARGET-SDK` assigned BLOCKER in both branches, collapsing the discoverability
  distinction the rule file explains.
- The Podfile deployment-target regex matched commented-out lines, and could not
  parse `platform :ios, min_ios_version_supported` at all.

### Fixed — false positives that fired fleet-wide
- Firebase config files (`GoogleService-Info.plist`, `google-services.json`)
  were BLOCKER "hardcoded credentials". They ship by design; the keys are public
  client identifiers. Hit 47 of 34 scanned projects' config files.
- Debug source sets are no longer scored as shipping code (20 projects).
- `CRASH-PII` matched the word `name` — i.e. the analytics event-name key — so
  it fired on the very code that was scrubbing PII.
- ATT is no longer required when ad-identifier collection is explicitly disabled.

### Fixed — wrong guideline citations
Verified against the 8 Jun 2026 guidelines. `2.5.13` is facial recognition and
`2.5.14` is recording consent (both were mislabelled); crypto mining is `2.4.2`,
not `2.5.18`; `3.1.6` and `3.1.7` do not exist, and Apple Pay is `4.9`; `1.4.4`
is DUI checkpoints with dangerous activity at `1.4.5`; `4.2.3` is app
independence, not offline capability; the loan-APR limit is `3.2.2(ix)`, an
*unacceptable* model rather than an acceptable one. Two of these had propagated
into scanner output. A test now pins them.

### Fixed — policy claims that were wrong
- **§3.1.1 was backwards for the US.** Current 3.1.1(a) says the entitlements
  are "not required" for external purchase links on the United States
  storefront. The old text called a legal monetization path a release blocker.
- **1.2 random/anonymous chat** was written as a moderation obligation. Apple's
  text is a prohibition — such apps "may be removed without notice."
- Texas SB 2420 (4 Jun 2026) was missing from the Declared Age Range table; the
  Brazil Play date had been merged into an Apple row.
- Geofencing was removed as an approved foreground-service use case
  (compliance 27 Jan 2027); 16 KB alignment has a hard date (1 Feb 2027);
  `READ_CALL_LOG` is no longer permitted for phone-call account verification.

### Added — upload gates the scanners could not produce
- `UIWEBVIEW` — ITMS-90809, an error since Dec 2020. Deliberately reaches into
  `Pods/` and `node_modules/`, which every other pass skips, because on bare RN
  that is where the offending code lives.
- `ICON-NAME-MISSING` — ITMS-90713, empty `CFBundleIconName`.
- `ABI-NO-64BIT` — Play has required 64-bit since Aug 2019.
- `KEYSTORE-COMMITTED` — release keystores tracked in git.
- `AGP-TOO-OLD` — an AGP that cannot build an AAB or target a modern API means
  the `TARGET-SDK` finding is a build-system migration, not a one-line change.
- `PRIVACY-MANIFEST-EMPTY` — reads the manifest instead of only checking that
  the file exists.
- `DEPLOYMENT-TARGET-OLD` now reads `IPHONEOS_DEPLOYMENT_TARGET` from the
  pbxproj, which bare RN checks in and nothing previously read.

### Added — infrastructure
- `.github/workflows/test.yml`. The README had claimed CI existed; it did not.
  It runs the suite on Python 3.8 and 3.12, asserts the scanners import nothing
  outside the standard library, fails on `docs/CHECKS.md` drift, checks the two
  manifests agree on version, and fails on unreplaced `<you>` placeholders.
- Removed the stray root `CHECKS.md`, a duplicate that had already drifted from
  the generated `docs/CHECKS.md`.

### Fixed — false positives found by scanning a 34-project fleet
Running both scanners across the whole portfolio before release surfaced seven
more, including one regression introduced by the merged-manifest fix in this
same release:
- **AGP writes four copies of the merged manifest** (`merged_manifest`,
  `merged_manifests`, `bundle_manifest`, `packaged_manifests`). Opening
  `build/intermediates` reported every permission five or six times over. The
  carve-out is now narrowed to `merged_manifests`, and a permission produces one
  finding however many copies contain it.
- **React Native's public debug keystore** (`android` / `androiddebugkey`) was
  reported as a leaked credential. It shipped in every project, and was half of
  all signing findings.
- **`keyAlias` is a name, not a secret** — another third of them.
- **Google `AIza` client keys** were BLOCKER "hardcoded credentials", 90 of 106
  fleet-wide. They ship in the binary by design and are secured by bundle-ID
  restriction, not secrecy. Now `MAPS-KEY-RESTRICTION`, MEDIUM, one per project,
  advising the thing that actually matters.
- **Editor local-history trees** (`.history/`, from the VS Code extension) are
  timestamped copies of every file, so one key was reported eight times.
- **Constants whose value is their own name** — `SUBMIT_SEND_CLIENT_NEW_PASSWORD
  = 'SUBMIT_SEND_CLIENT_NEW_PASSWORD'` is a Redux action type.
- **Translated UI labels** — `Certificate_password: 'Zertifikats-Passwort'`.

Fleet totals before and after these fixes: 1599 → 949 findings, BLOCKERs
242 → 152, and `SECRET-HARDCODED` 108 → 14 across 6 projects. The surviving
BLOCKERs were inspected individually: committed AWS keys, Google Play
service-account private keys, and `UIWebView` in vendored pods.

### Tests
29 → 69. Every fix above is pinned, and each false-positive fix is paired with a
guard asserting the real finding is still caught.

## [2.3.0] — 2026-09-21

Bare React Native (CLI) support. Earlier versions were written Expo-first, which
under-checked CLI projects — the common case. A bare project checks `ios/` and
`android/` into the repo, so there is *more* to verify, not less.

### Added — checks that only apply to bare RN
- `POD-PRIVACY-MANIFESTS` — enumerates third-party pods from `Podfile.lock`. Apple requires SDKs on its commonly-used list to ship a privacy manifest and signature; a stale pod that lacks one fails validation at upload, and the error names the pod rather than the RN package that pulled it in.
- `DEPLOYMENT-TARGET-OLD` — an old iOS target silently pins old pod versions, which is how projects end up without privacy manifests.
- `ENTITLEMENTS-REVIEW` — HealthKit, VPN, Family Controls, associated domains and iCloud entitlements flagged for justification. An entitlement with no matching feature is a rejection.
- `NDK-VERSION` — 16 KB page alignment needs NDK r27+. Bare projects pin `ndkVersion` directly; managed Expo doesn't expose it.
- `SIGNING-SECRET-COMMITTED` — keystore passwords hardcoded in `gradle.properties` or `build.gradle`. The RN CLI template uses `MYAPP_RELEASE_STORE_PASSWORD`, so this is easy to commit by accident.
- `LOCAL-PROPERTIES-TRACKED` — `android/local.properties` present and not gitignored.

### Fixed
- The signing-secret check missed `STORE_PASSWORD` (UPPER_SNAKE), which is exactly the RN CLI template's convention — so it would have missed the real-world case while catching the camelCase one. Found by testing against a bare fixture.
- `PRIVACY-MANIFEST` correctly reports HIGH when `ios/` exists, rather than the managed-Expo `UNVERIFIED` downgrade.

### Changed
- Both package-map references now lead with the bare RN column and carry a "what you own that Expo would have generated" section.
- Both `SKILL.md` profile phases assume bare RN unless evidence says otherwise.

### Tests
- 9 new tests (29 total), including one asserting the scanner never prints a discovered credential into its own output, and one asserting an env-var signing config is *not* flagged.

## [2.2.0] — 2026-09-21

Documentation and release tooling. No rule or severity changes.

### Added
- `docs/CHECKS.md` — every check both scanners can emit (49), with severity and the guideline or policy each maps to. Generated from the scanner source by `scripts/gen_checks.py`; CI fails if it drifts.
- `scripts/prepare_release.py` — fills the `<you>` placeholders, author and marketplace name in one command, with `--dry-run`.
- README: Requirements, Example output, Troubleshooting, Uninstall, Versioning, Contributing.
- Explicit statement that the scanners are read-only, make no network calls and write nothing — they are safe to run on proprietary or client code.

## [2.1.0] — 2026-09-21

Validated against a real production React Native codebase for the first time
(bluesky-social/social-app — Expo, ships to both stores, ~124 MB). That run
produced 5 false HIGH findings on compliant code. All are fixed and covered by
regression tests.

### Fixed — false positives found on real code
- `@braintree/sanitize-url`, a URL sanitiser, matched the `braintree` substring and was reported as a payment SDK (3 false HIGHs). Payment SDK detection now matches exact package names.
- The English word "adjust" ("we adjust the offset", "adjust the pref") matched the `react-native-adjust` analytics SDK, producing a false `ATT-MISSING`. All SDK patterns are now exact package names.
- `rate\s+us` matched inside "sepa**rate us**er", flagging a custom rating prompt in a telemetry file. Rating-prompt detection now uses word boundaries.
- Managed Expo projects have no `ios/` directory, so the privacy manifest legitimately isn't in source — it appears at prebuild. Reported as HIGH; now a MEDIUM `PRIVACY-MANIFEST-UNVERIFIED` telling you to check after prebuild.
- Storybook, `__mocks__` and `.stories.` paths are now treated as non-production, like tests.

### Changed
- Rules describing one condition (`OTA-UPDATES`, `WEBVIEW-SHELL`, `TRACKING-SDK`, `PAYMENT-SDK`, `CONSOLE-LOG`) report once with a roll-up count instead of once per occurrence. `OTA-UPDATES` alone fired 5 times for a single integration.

### Added
- 6 regression tests pinning each false positive above.
- CI (Python 3.8 + 3.12), `.gitignore`, `CHANGELOG.md`, executable bits and a Python version guard on both scanners.

**Result on the same real codebase after fixes: 0 BLOCKER, 0 HIGH on both platforms.**

## [2.0.0] — 2026-09-21

### Added
- `rn-android-review` skill: Play Developer Program Policies, Console upload gates (target API level, Play Billing floor, AAB, 16 KB page alignment), Data safety, restricted permissions, foreground service types.
- `references/ios-android-divergences.md` — the four places the stores genuinely require different behavior.
- `/review-android` and `/review-stores` commands.
- Android scanner (`skills/rn-android-review/scripts/scan.py`).
- Test suite covering both scanners.

### Fixed — corrections found by verifying against live sources
- **Apple does have an upload gate.** Earlier text claimed Apple had no equivalent of Play's target API floor. Apple requires builds against the iOS 26 SDK (since 28 Apr 2026) and answered age-rating questions (due 31 Jan 2026). Added an "Upload gates" section to `2-performance.md` and corrected the divergences file and README.
- **4.3 Spam** rewritten per the 8 Jun 2026 guideline revision: named "well established" categories, removal risk for apps that don't attract customers, Developer Program consequences for repeated low-effort submissions.
- **1.2 UGC** now notes the 6 Feb 2026 clarification that random and anonymous chat apps are in scope.
- **Age assurance** was absent entirely. Added Declared Age Range (entitlement, iOS 26+, AU/BR/SG/UT/LA dates) and the Play Age Signals counterpart.

## [1.0.0] — 2026-09-21
- Initial release: `rn-ios-review` skill, iOS scanner, `/review-ios`.
