---
description: Full dual-store audit — Apple App Store and Google Play — for a React Native app
argument-hint: "[path to project root, defaults to cwd]"
---

Run a complete dual-store review of the React Native / Expo project at `$1` (default: the current working directory).

Use both skills: `rn-ios-review` and `rn-android-review`.

Order of work:

1. **Shared profile, once.** Expo vs bare, SKU classification (digital vs physical/real-world service), the SDK inventory, data types collected, accounts, UGC, health data, background work. These facts are platform-independent — establish them before branching.
2. **Play upload gates first.** `python3 skills/rn-android-review/scripts/scan.py <path>` — target API level, Play Billing version, AAB, 16 KB alignment. These have the longest lead time and don't care that Apple approved the same release.
3. **iOS audit.** `python3 skills/rn-ios-review/scripts/scan.py <path>` plus the relevant `rn-ios-review` rule files.
4. **Android policy audit.** The relevant `rn-android-review` rule files.
5. **Reconcile divergences.** Read `skills/rn-android-review/references/ios-android-divergences.md` and check the points where the two stores genuinely require different behavior: payments and `Platform.OS` branches, the three privacy declarations (App Privacy, `PrivacyInfo.xcprivacy`, Data safety) against one SDK inventory, account deletion (in-app vs in-app + web URL), and CSAE.

Produce **one report** with a shared verdict, then per-store findings, then an explicit divergences section. Don't average the two rulebooks — where they disagree, say so and give the per-platform fix.
