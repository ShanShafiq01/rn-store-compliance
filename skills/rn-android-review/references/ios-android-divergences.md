# Where Apple and Google Genuinely Disagree

Read this before "fixing" one platform's behavior into the other. The instinct in a React Native codebase is to make both platforms identical; on these points that instinct produces a violation on one store.

When reporting, name the divergence explicitly rather than averaging the two rules.

## 1. Payments — the big one

| | Apple | Google |
|---|---|---|
| Digital goods | StoreKit required | Play Billing required |
| Linking out to pay | Prohibited without a specific entitlement (External Purchase Link / Link Entitlement), which dictates the exact UI and disclosure | Permitted under alternative and user-choice billing programs in several jurisdictions, each with its own API, fee treatment, and disclosure UI |
| Physical goods / real-world services | Must **not** use IAP | Must **not** use Play Billing |
| Version floor enforcement | None — StoreKit is part of the SDK | Play Billing Library has a rolling ~2-year life; below the floor, the **upload is rejected** |

**What this means for the code**: the Android and iOS checkout paths legitimately differ. Audit each `Platform.OS` branch against its own store's rule. A single shared checkout that satisfies Apple will usually be over-restricted on Android, and one that satisfies Google may be a 3.1.1 rejection on iOS.

**What stays the same**: the classification of the SKU. A digital subscription is digital on both; a clinical consult with a human is a real-world service on both. Classify once, then branch.

## 2. Data disclosure — same facts, two artifacts

| | Apple | Google |
|---|---|---|
| Form | App Privacy answers in App Store Connect | Data safety form in Play Console |
| In-binary artifact | `PrivacyInfo.xcprivacy`, incl. approved reasons for required-reason APIs | none |
| Tracking consent | ATT prompt required before cross-app tracking | No equivalent prompt; `AD_ID` permission must be declared |
| Privacy policy | Required, in-console and in-app | Required, in-console and in-app |

One SDK inventory must produce three consistent declarations (App Privacy, privacy manifest, Data safety). Mismatch between them is itself a violation on both sides, and it's the most common finding in a dual-store audit because the two forms are usually filled out months apart by different people.

## 3. Account deletion

| Apple | Google |
|---|---|
| In-app deletion required | In-app deletion **and** a publicly accessible web deletion URL declared in Console |

Teams that satisfy only one get caught by the other. Build the web endpoint — it satisfies Google and doesn't hurt Apple.

## 4. Version and SDK floors — both stores have them

| | Apple | Google |
|---|---|---|
| What's enforced | Minimum **build SDK**: since 28 Apr 2026 every new submission and update must be built with the iOS 26 / iPadOS 26 SDK | Minimum **target API level**: API 36 for new uploads since 31 Aug 2026, API 35 to stay discoverable |
| Cadence | Roughly annual, tied to the OS release | Every August |
| What breaks when you raise it | Xcode/toolchain upgrade, RN and pod compatibility | Edge-to-edge becomes mandatory, `onBackPressed` stops firing, foreground service types tighten |

Both gate the upload, and both can fail a release months after the last successful one with no code change. They are not equivalent in *kind* — Apple pins the SDK you compile against, Google pins the API level you declare as your target — so a project can satisfy one and fail the other. Track both as calendar items.

For a React Native project, Apple's SDK floor usually means an Xcode and RN version bump; Google's target floor usually means layout and navigation work. Neither is an afternoon.

## 5. UGC and child safety

Both require filtering, reporting, blocking, and contact info. Google additionally requires **CSAE standards** with published in-app reporting and a point of contact for apps with social features — a declaration Apple doesn't ask for and RN teams routinely miss.

## 6. OTA updates

Both permit JS-level OTA updates for fixes and content, and both prohibit using them to ship behavior that wasn't reviewed. Apple cites 2.3.1 / 2.5.2; Google cites Device and Network Abuse. Same rule, same fix — this one does *not* diverge, despite the folklore that Apple is stricter.

## 7. Minimum functionality

Apple 4.2 and Play's spam policy both reject thin WebView wrappers. Apple enforces it more aggressively at review; Google more often lets it publish and removes it later. Don't read Google's initial acceptance as clearance.

## 8. Permissions model

| Apple | Google |
|---|---|
| Purpose strings in Info.plist, reviewed by a human for specificity | Runtime prompts plus **Console declarations** for restricted permissions, some requiring a demo video |
| Vague string → rejection | Undeclared restricted permission → removal |

Apple checks how you *describe* the permission; Google checks whether you *qualify* for it. Both need the underlying feature to actually exist.

---

## Auditing a dual-store release

1. Classify SKUs, SDKs, and data types once — these are shared facts.
2. Branch the audit at payments, disclosure artifacts, deletion, and permissions.
3. Reconcile the three privacy declarations against one SDK inventory before submitting either store.
4. Check Play's upload-time gates first; they have the longest lead time to fix and they don't care that Apple approved the same release.
