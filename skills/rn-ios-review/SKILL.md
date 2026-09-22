---
name: rn-ios-review
description: Audits a React Native or Expo codebase against Apple's App Store Review Guidelines, producing a severity-ranked rejection-risk report with file:line evidence and concrete fixes. Use this skill whenever the user mentions App Store review, app rejection, submission readiness, "will my app get rejected", TestFlight-to-App-Store promotion, StoreKit/IAP compliance, App Tracking Transparency, privacy manifests (PrivacyInfo.xcprivacy), Info.plist purpose strings, account deletion requirements, or is preparing a React Native/Expo iOS release. Also use it when reviewing a PR that touches payments, permissions, tracking, user-generated content, health data, WebViews, or OTA updates in an RN iOS app.
license: MIT
metadata:
  author: Bitsol Technologies
  version: 1.0.0
  platform: iOS (React Native / Expo)
  guidelines_current_through: Apple App Store Review Guidelines, incl. the 6 Feb 2026 and 8 Jun 2026 revisions; verified against Apple Developer news, Sept 2026
---

# React Native iOS App Review Auditor

Evaluates a React Native or Expo codebase against Apple's App Store Review Guidelines, sections 1–5, and reports what would get the build rejected.

Scoped to iOS only. Most of what Apple rejects for is visible in the source tree — a missing restore-purchases control, a vague purpose string, a tracking SDK that initializes before the ATT prompt — so a code-level audit catches the majority of it before a reviewer does.

## Workflow

### Phase 1 — Profile the app (2 min)

**Assume bare RN (CLI) unless the evidence says otherwise** — most teams use it, and it puts `ios/` and `android/` in the repo, which means more is checkable than in a managed Expo project, not less.

Answer these first; they decide which rule files matter and stop the audit from covering the wrong app:

| Question | How to check | What it unlocks |
|---|---|---|
| Expo or bare RN (CLI)? | `app.json` / `app.config.*` vs an `ios/` dir | Where Info.plist and entitlements actually come from |
| Managed, prebuild, or ejected? | `ios/` present alongside Expo config | Whether to audit the template or the generated output |
| Does it take money? | `react-native-iap`, `react-native-purchases`, `@stripe/stripe-react-native` | `3-business.md` |
| Accounts / login? | auth SDKs, `signUp`, `createUser` | Account **deletion** requirement (5.1.1(v)) |
| Social login? | Google/Facebook/Apple sign-in | 4.8 login alternative |
| User-generated content? | posts, comments, chat, uploads, profile photos | `1-safety.md` |
| Health, medical, or PHI? | HealthKit, FHIR, patient/vitals models | `health-and-regulated.md` — **read it if yes** |
| Kids / under-13? | age gates, COPPA copy, category | Kids rules in 1.3 and 5.1.4 |
| Ads or analytics SDKs? | Firebase, AppLovin, AppsFlyer, Amplitude, Sentry | ATT + App Privacy + privacy manifest |
| WebView-heavy? | `react-native-webview` as the main screen | 4.2 minimum functionality |
| OTA updates? | `expo-updates`, CodePush | 2.3.1 / 2.5.2 |

Write the answers into the report header so a reader knows what was in scope.

### Phase 2 — Automated scan

From the project root:

```bash
python3 scripts/scan.py /path/to/rn-project --format markdown
```

Read-only, stdlib-only, grep-based. Surfaces `file:line` evidence for hardcoded secrets, dynamic code execution, external payment paths, insecure token storage, tracking SDKs with no ATT call, missing `PrivacyInfo.xcprivacy`, vague or empty purpose strings, missing account-deletion and UGC-moderation paths, custom rating prompts, cross-platform copy, and `NSAllowsArbitraryLoads`.

Treat it as a **lead generator, not a verdict**. A `sk_live_` string in a fixture is not a rejection, and a clean scan is not compliance — the highest-value findings are structural (moderation that exists on paper only, a client-trusted entitlement flag, App Privacy answers that contradict the SDK list) and no grep will find them.

### Phase 3 — Rule-by-rule review

Load only the files the profile flagged:

| File | Covers |
|---|---|
| `rules/1-safety.md` | Objectionable content, UGC moderation, Kids Category, physical harm, data security |
| `rules/2-performance.md` | Completeness, demo accounts, metadata, OTA updates, private APIs, background modes |
| `rules/3-business.md` | StoreKit/IAP, subscriptions, restore, external purchase links, reader apps, crypto |
| `rules/4-design.md` | Copycats, minimum functionality, spam, 4.8 login alternatives, mini-apps, Apple Pay |
| `rules/5-legal.md` | Privacy policy, purpose strings, ATT, privacy manifests, account deletion, IP, VPN, MDM, 5.6 |
| `rules/health-and-regulated.md` | Health/HealthKit rules plus the HIPAA-adjacent layer Apple doesn't check |
| `references/rn-package-map.md` | Expo ⇄ bare RN package equivalents for each requirement |
| `../rn-android-review/references/ios-android-divergences.md` | Where Apple and Google genuinely disagree — read this if the app also ships to Play, before "fixing" one platform into the other |

For each finding capture: **guideline number → evidence (`file:line`) → why it rejects → the fix**. A finding without a file reference is an opinion, and engineers discount those.

### Phase 4 — Report

Use `references/report-template.md`. Order by severity, never by file order — the reader is deciding what blocks the release.

## Severity model

| Severity | Meaning | Examples |
|---|---|---|
| **BLOCKER** | The upload fails, or rejection is near-certain; the ship date moves | Build SDK below Apple's floor, unanswered age-rating questions, external payment for digital goods (3.1.1), private API usage (2.5.1), `eval` of remote code (2.5.2), no privacy policy (5.1.1), on-device mining (2.4.2) |
| **HIGH** | Commonly cited rejection | Tracking SDK with no ATT prompt (5.1.2), accounts with no in-app deletion (5.1.1(v)), IAP with no restore, UGC with no report/block (1.2), missing privacy manifest, no demo account for a gated app (2.1) |
| **MEDIUM** | Reviewer discretion; often the second-pass rejection | Vague purpose strings (5.1.1(ii)), over-broad permissions, unjustified background modes (2.5.4), WebView-thin functionality (4.2), custom rating prompts (5.6.1) |
| **LOW** | Polish | `console.log` in release paths, Android references in copy (2.3.10), deprecated APIs |

## RN/Expo-specific traps

These cause more rejections in React Native codebases than anything Swift-specific:

- **The JS bundle is readable.** Anything in `.env`, `react-native-config`, or `Constants.expoConfig.extra` ships in plaintext inside the IPA. Apple cites 1.6 / 2.5.x; it is also a real security finding.
- **Config plugins generate the native config.** Purpose strings, entitlements, and `UIBackgroundModes` come from `app.json` plugin props, and plugin defaults ship vague strings that fail 5.1.1(ii). Audit the Info.plist produced by `expo prebuild`, never the template.
- **SDKs collect at import time.** ATT must be requested *before* any tracking SDK initializes. Many RN analytics modules start collecting in their module constructor, so a correctly-placed `requestTrackingPermissionsAsync()` in a screen component is already too late. Check the import graph from `index.js`.
- **Don't normalize the iOS checkout to match Android.** Google permits alternative billing in several jurisdictions; Apple does not without an entitlement. The two branches are supposed to differ — see the divergences reference before consolidating them.
- **`Platform.OS` branches hide violations.** A compliant Android checkout and a non-compliant iOS one live in the same function. Read the iOS branch specifically, including WebView and deep-link fallbacks.
- **OTA updates are allowed until they aren't.** `expo-updates` and CodePush are fine for bug fixes and content. Shipping new features or new data collection past review violates 2.3.1 and 2.5.2. Assess what the update channel actually ships, not what the library is capable of.
- **Android code in an iOS submission.** Copy strings like "also available on Google Play", Play Store links, and Android-only UI that renders on iOS all trip 2.3.10.
- **Transitive native modules pull entitlements.** A dependency can add background modes or HealthKit entries you never requested. Diff the generated Info.plist against the previous release.

## Reviewing without the repo

If the user only describes the app or shares screenshots, still produce the audit — mark evidence as `reported` rather than `file:line`, and list which files would confirm each item. Say plainly what couldn't be verified; an audit implying coverage it doesn't have is worse than a short one.

## References

- App Store Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
- Privacy manifest files: https://developer.apple.com/documentation/bundleresources/privacy-manifest-files
- App Tracking Transparency: https://developer.apple.com/documentation/apptrackingtransparency
- App Store Connect Help: https://developer.apple.com/help/app-store-connect/
- Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/

Apple revises the guidelines several times a year. When a finding hinges on a specific rule number, entitlement, or requirement date, check it against the live guidelines before reporting it as a blocker — the content here is accurate as of the date in the frontmatter and nothing more.
