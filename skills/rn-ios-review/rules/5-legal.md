# Apple Section 5 — Legal

Highest rejection volume of any section, and nearly all of it is verifiable from the repo.

## 5.1.1 Data collection and storage

**(i) Privacy policy** — required, linked in App Store Connect *and* accessible in-app. Must identify what data is collected, how, and all third parties with access (name the SDKs), plus data retention/deletion policy.

**(ii) Permission and purpose strings.** Every permission needs a specific, honest `NSXxxUsageDescription`. Generic strings are a standard rejection.

```xml
<!-- 🟠 too vague -->
<key>NSCameraUsageDescription</key>
<string>This app needs camera access</string>

<!-- ✅ specific -->
<string>Take a photo of your insurance card so we can attach it to your claim.</string>
```
In Expo these live in `app.json` → `ios.infoPlist` or are injected by config plugins (`expo-camera`, `expo-location`). Verify the **generated** Info.plist after prebuild — plugin defaults are often the vague string.

**(iii) Data minimization** — only request what a feature genuinely needs. Requesting contacts or precise location "for future use" is a rejection.

**(iv) Access** — don't require an account for features that don't need one; don't require unnecessary personal info to register.

**(v) Account sign-in** — if the app supports account creation, it must support **account deletion in-app**. Linking out to a web form is not sufficient.

```ts
// 🔴 HIGH
Linking.openURL('https://example.com/delete-account');
// ✅ in-app flow that actually deletes, with confirmation
await api.delete('/account');
```
For regulated data the app may retain records for a legally required period — say so in the flow; the requirement is that deletion is *initiated* in-app.

**(vi–ix)** Third-party integrations, consent for data sharing, no covert collection.

## 5.1.2 Data use and sharing

**App Tracking Transparency.** If the app tracks the user across apps/websites owned by other companies, or shares data with data brokers, it must request permission via ATT and respect the answer. An analytics or ads SDK that collects IDFA without an ATT prompt is a HIGH-to-BLOCKER finding.

```ts
// ✅ Expo
import { requestTrackingPermissionsAsync } from 'expo-tracking-transparency';
const { granted } = await requestTrackingPermissionsAsync();
if (granted) analytics.setAnalyticsCollectionEnabled(true);
```
Also required: `NSUserTrackingUsageDescription` in Info.plist. And ATT must be requested **before** any tracking SDK initializes — check import-time side effects, which is where RN apps fail: many SDKs start collecting in their module constructor.

Apps must not derive data from a permission for an unrelated purpose (contacts pulled for "friend finding" then used to build a marketing graph).

## 5.1.3 Health and HealthKit

HealthKit/health data must not be used for advertising, marketing, or sale to data brokers, and must not be stored in iCloud. Apps must provide a privacy policy specific to health data. Human-subject research requires ethics-board approval and consent.

See `health-and-regulated.md` for the full treatment, including HIPAA-adjacent considerations.

## 5.1.4 Kids and age assurance

COPPA/GDPR-K compliance; no behavioral advertising; verifiable parental consent where required.

**Age assurance is now a live submission gate, not just a policy.** Two separate things:

**Age ratings.** The rating system was expanded from 4+/9+ to 4+/9+/13+/16+/18+, with new questions about sensitive content and the ability to set a higher minimum. Responses to the updated questions were due 31 January 2026 — an app that hasn't answered them is blocked from submitting updates in App Store Connect. Check this before anything else; it's a two-minute fix that silently blocks a release.

**Declared Age Range API.** Regional laws now require age confirmation, and Apple exposes a signal for it:

| Region | From | What applies |
|---|---|---|
| Australia, Brazil, Singapore | 24 Feb 2026 | App Store blocks 18+ downloads unless the user is confirmed an adult; the store does this automatically, but developers may have separate obligations |
| Brazil — loot boxes | 24 Feb 2026 | Loot boxes trigger an **18+ rating**; apps containing them must be updated accordingly |
| Utah (App Store Accountability Act) | 6 May 2026 | Age categories shared for new Apple Accounts via the API |
| Louisiana | 1 Jul 2026 | Same |
| **Texas (SB 2420)** | **4 Jun 2026** | The injunction was lifted. New Texas Apple Accounts need age assurance and **guardian consent for downloads, IAP, and significant app updates**. Apple's earlier "Texas paused" notice is superseded — check you are not reading it |

Note: **17 Mar 2026 is the Play Age Signals / Brazil Digital ECA date, not an Apple date.** The two stores have separate regimes and separate deadlines; merging them into one row is a common and expensive mistake.

Three companion obligations that are easy to miss:
- **PermissionKit `SignificantAppUpdateTopic`** — *you* decide and declare when one of your own updates is "significant" enough to re-trigger guardian consent.
- **StoreKit `AppStore.ageRatingCode`** — read the rating the store applied.
- **App Store Server Notifications for consent withdrawal** — a guardian revoking consent is a server-side event you must handle. This is an obligation outside the app binary entirely.

```ts
// Requires the com.apple.developer.declared-age-range entitlement,
// requested from Apple BEFORE submission. The base API is iOS 26, but the fuller
// age-assurance fields (confirmation method, parental-control status) need the
// iOS/iPadOS 26.2 SDK and Xcode 26.2.
<key>com.apple.developer.declared-age-range</key><true/>
```

RN implications: the framework is iOS 26+ only, so a bare-RN app needs a native module or a community package, and the entitlement has lead time — request it early. The API also signals whether the user is *required* to share an age range and whether guardian permission is needed for significant updates. Handle `notAvailable` as neither a pass nor a fail; treating refusal as a completed check is the common implementation bug.

If the app is 18+ or ships to any of the regions above, this belongs in the report as a HIGH, not a footnote.

## 5.1.5 Location
Don't use location for anything the user hasn't been told about. Only request "Always" when core functionality requires it; prefer "When In Use". Emergency services must not depend solely on location.

```ts
// 🟠 requesting Always with no background feature
Location.requestBackgroundPermissionsAsync();
```

## Privacy manifests (`PrivacyInfo.xcprivacy`)

Apps and third-party SDKs on Apple's commonly-used-SDK list must ship a privacy manifest declaring collected data types, tracking domains, and **approved reasons for required-reason APIs** (file timestamps, system boot time, disk space, active keyboards, `UserDefaults`). RN itself, Expo modules, and most analytics SDKs now ship manifests; verify:

- your app target has a `PrivacyInfo.xcprivacy`
- every third-party SDK version in use ships one (stale pods are the usual gap)
- declared data types match your App Store Connect App Privacy answers exactly

Mismatch between the manifest, App Privacy, and the code is itself a finding.

## 5.2 Intellectual property
No unlicensed content, no third-party trademarks in name/icon, no scraping. Fonts, icon packs and audio in `assets/` need licenses — check `package.json` deps for copyleft conflicts too.

## 5.3 Gaming, gambling, lotteries
Real-money gaming needs licensing, geo-restriction (real location checks, not a locale string), and must be free to download.

## 5.4 VPN apps
Must use `NEVPNManager`, be offered by an enrolled organization, declare data collection, and must not sell/share data.

## 5.5 Mobile device management
MDM requires commercial-enterprise/education justification and must not sell data. A subset of MDM capabilities (parental controls, device security) has narrower allowances.

## 5.6 Developer code of conduct

- **5.6.1 Review prompts must use the system API only.** Custom "Rate us 5 stars!" modals are a violation.
  ```ts
  // 🔴
  Alert.alert('Enjoying the app?', 'Please leave us 5 stars!');
  // ✅
  import * as StoreReview from 'expo-store-review';
  await StoreReview.requestReview();
  ```
- 5.6.2 Developer identity accuracy
- 5.6.3 No discovery/search/chart manipulation, incentivized installs, or fake reviews
- 5.6.4 App quality — repeated policy-violating submissions can cost account standing

---

## Checklist

- [ ] Privacy policy linked in App Store Connect and reachable in-app
- [ ] Policy names the third-party SDKs with data access and states retention/deletion
- [ ] Every purpose string specific to its actual use, verified in the generated Info.plist
- [ ] Only permissions the features require; no speculative requests
- [ ] In-app account deletion if accounts exist
- [ ] ATT implemented before any tracking SDK initializes; `NSUserTrackingUsageDescription` present
- [ ] App Privacy answers ≡ privacy manifest ≡ the actual SDK inventory
- [ ] `PrivacyInfo.xcprivacy` present with required-reason API declarations; SDKs up to date
- [ ] Updated age rating questions answered in App Store Connect (blocks submission if not)
- [ ] Declared Age Range handled if 18+ or shipping to AU/BR/SG/UT/LA/**TX**; entitlement requested
- [ ] Consent-withdrawal notifications handled server-side
- [ ] Health data not used for ads, not synced to iCloud
- [ ] "Always" location only where a background feature requires it
- [ ] Licensed fonts, icons, audio; no third-party marks in name/icon
- [ ] Gambling geo-restricted by real location and licensed
- [ ] VPN uses `NEVPNManager`; MDM justified
- [ ] Rating prompts use `StoreReview` only
