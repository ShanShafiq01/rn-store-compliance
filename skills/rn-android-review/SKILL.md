---
name: rn-android-review
description: Audits a React Native or Expo codebase against Google Play's Developer Program Policies and Play Console technical requirements, producing a severity-ranked report with file:line evidence and fixes. Use this skill whenever the user mentions Play Store review, Play policy, app suspension, Data safety form, target API level, Play Billing, targetSdkVersion, 16 KB page size, AAB upload rejection, restricted Android permissions, background location declaration, account deletion URL, foreground service types, or is preparing a React Native/Expo Android release. Also use it when reviewing a PR that touches permissions, the AndroidManifest, billing, ads, tracking, user-generated content, or background work in an RN Android app.
license: MIT
metadata:
  author: Bitsol Technologies
  version: 1.0.0
  platform: Android (React Native / Expo)
  guidelines_current_through: Google Play Developer Program Policy and Play Console requirements; target API and Billing floors verified Sept 2026, policy text not independently re-verified
---

# React Native Android Play Review Auditor

Evaluates a React Native or Expo codebase against Google Play's Developer Program Policies and the Play Console requirements that gate an upload.

Scoped to Android. The failure modes differ from Apple's in a way that changes how you audit:

- **Play rejects at upload time** for target API level, Billing Library version, AAB format, and 16 KB alignment. No human sees the build. These block the release outright, so check them first.
- **Play enforces after publication.** Policy violations surface as warnings, removals, or suspensions, and repeated violations reach the developer account. A shipped app is not a cleared app.
- **Much of compliance lives in the Console, not the code.** The Data safety form, permission declarations, and content rating are separate artifacts that must agree with what the code actually does. A truthful app with a wrong form is still a violation.

## Workflow

### Phase 1 — Profile the app (2 min)

**Assume bare RN (CLI) unless the evidence says otherwise** — most teams use it, and it puts `ios/` and `android/` in the repo, which means more is checkable than in a managed Expo project, not less.

| Question | How to check | What it unlocks |
|---|---|---|
| Expo or bare RN (CLI)? | `app.json` / `app.config.*` vs an `android/` dir | Where manifest and gradle values come from |
| Managed, prebuild, or ejected? | `android/` present alongside Expo config | Whether to audit the template or the generated output |
| Does it take money? | `react-native-iap`, `react-native-purchases`, `@stripe/stripe-react-native` | `3-monetization.md` |
| Accounts / login? | auth SDKs, `signUp`, `createUser` | Account deletion — **in-app and a public web URL** |
| User-generated content? | posts, comments, chat, uploads | `1-restricted-content.md`, incl. CSAE |
| Health, medical, or PHI? | Health Connect, FHIR, patient models | `health-and-regulated.md` |
| Kids / mixed audience? | age gates, COPPA copy, category | Families policy, `AD_ID` |
| Ads or analytics SDKs? | AdMob, AppLovin, AppsFlyer, Firebase, Sentry | Data safety + ads policy |
| Background work? | background fetch, geolocation, audio, uploads | Foreground service types |
| Native modules with `.so` files? | camera, ML, MMKV, SQLite, Reanimated | 16 KB page alignment |

### Phase 2 — Automated scan

```bash
python3 scripts/scan.py /path/to/rn-project --format markdown
```

Read-only, stdlib-only. Surfaces `file:line` evidence for hardcoded secrets, dynamic code execution, external payment paths, insecure storage, cleartext traffic, restricted permissions in the manifest, `targetSdkVersion`, Play Billing version, missing `foregroundServiceType`, APK-only build config, missing account-deletion and UGC-moderation paths, and the SDK inventory the Data safety form has to match.

Treat it as a lead generator. The scanner reads the **source** manifest; the one that ships is the **merged** manifest, and the difference is where transitive permissions hide. Build the app and re-check:

```bash
find android -path "*merged_manifests*" -name "AndroidManifest.xml"
```

### Phase 3 — Rule-by-rule review

| File | Covers |
|---|---|
| `rules/1-restricted-content.md` | Restricted content, UGC, CSAE, families policy, impersonation, deceptive behavior, spam |
| `rules/2-privacy-data.md` | Data safety form, sensitive and restricted permissions, photo/video policy, `AD_ID`, account deletion, device and network abuse |
| `rules/3-monetization.md` | Play Billing, alternative and user-choice billing, Billing Library floor, subscriptions, ads, gambling |
| `rules/4-technical-quality.md` | Target API level, 16 KB pages, AAB, foreground services, core vitals, Console declarations |
| `rules/health-and-regulated.md` | Health Connect restricted data, health claims, plus the HIPAA-adjacent layer Play doesn't check |
| `references/rn-package-map.md` | Expo ⇄ bare RN package equivalents per requirement |
| `references/ios-android-divergences.md` | Where Apple and Google genuinely disagree — read before "fixing" one platform into the other |

For each finding capture: **policy → evidence (`file:line` or Console artifact) → why it fails → the fix**.

### Phase 4 — Report

Use `references/report-template.md`. Order by severity. Keep upload-time blockers visually separate from policy findings — they need different people and different timelines.

## Severity model

| Severity | Meaning | Examples |
|---|---|---|
| **BLOCKER** | The upload fails or the app gets removed | `targetSdkVersion` below Play's floor, Billing Library below the enforced major version, APK instead of AAB, external payment for digital goods, unaligned `.so` files once enforcement lands |
| **HIGH** | Policy violation likely to trigger enforcement | Data safety form contradicting the code, accounts with no deletion path, background location with no declaration, UGC with no report/block, restricted permission with no qualifying use case, no privacy policy |
| **MEDIUM** | Enforcement risk or quality gate | Over-broad media permissions where the photo picker would do, permission prompts with no context, undeclared ads, ANR/crash vitals near threshold |
| **LOW** | Polish | `console.log` in release paths, deprecated APIs, unused permissions that are merely untidy |

## RN/Expo-specific traps on Android

- **The source manifest is not the shipped manifest.** Libraries merge in permissions you never requested — `READ_PHONE_STATE` from device-info libraries, `QUERY_ALL_PACKAGES` from several SDKs, location from map libraries. Audit the merged output and strip with `tools:node="remove"`.
- **Version floors are set by your wrapper, not your gradle.** The Play Billing Library version comes from `react-native-iap` or `react-native-purchases`; the NDK build that decides 16 KB alignment comes from each native dependency. Upgrading the wrapper is the fix; editing gradle usually isn't.
- **Raising `targetSdkVersion` is a project, not a line change.** API 36 makes edge-to-edge mandatory and stops `onBackPressed` firing. Budget for safe-area and navigation work, not an afternoon.
- **The JS bundle and `strings.xml` are extractable from the AAB.** Anything in `.env` or `react-native-config` ships in plaintext. Play Console flags leaked keys through security advisories.
- **One `.so` from an abandoned dependency blocks the whole release.** Find unaligned native libs early — replacing an unmaintained SDK takes weeks, not days.
- **`Platform.OS` branches hide violations.** Read the Android branch of the checkout specifically, including WebView and deep-link fallbacks.
- **Expo config plugins generate the manifest.** Permissions and service declarations come from `app.json` plugin props. Audit the output of `expo prebuild`, never the template.

## Reviewing without the repo

If the user only describes the app, still produce the audit — mark evidence as `reported`, and list which files or Console screens would confirm each item. Say plainly what couldn't be verified.

## References

- Play policy center: https://play.google.com/about/developer-content-policy/
- Target API level requirements: https://support.google.com/googleplay/android-developer/answer/11926878
- Play Billing deprecation schedule: https://developer.android.com/google/play/billing/deprecation-faq
- Data safety: https://support.google.com/googleplay/android-developer/answer/10787469
- 16 KB page size: https://developer.android.com/guide/practices/page-sizes

Play's version floors advance every August and the policy center changes several times a year. When a finding hinges on a specific date, API level, or library version, verify it against the live page before reporting it as a blocker — the numbers here are accurate as of the date in the frontmatter and nothing more.
