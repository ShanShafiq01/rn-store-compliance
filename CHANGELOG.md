# Changelog

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
