# Google Play — Privacy, Permissions, Data Safety

The Android half of the privacy audit. Google's enforcement hinges on one idea: **the Data safety form must match what the code actually does.** A mismatch is a policy violation independent of whether the underlying collection was acceptable.

## Data safety section

Required for every app. Declares, per data type: whether it's collected, whether it's shared, whether collection is optional, why, and whether it's encrypted in transit and deletable.

**How to audit it from the repo**: build the SDK inventory first, then check the declaration against it.

```bash
# every network/analytics/ads/auth SDK is a data-safety line item
grep -E "firebase|amplitude|mixpanel|segment|sentry|bugsnag|facebook|applovin|admob|onesignal|branch|appsflyer|adjust|datadog" package.json
```
Each of those collects something. Sentry and Bugsnag collect device IDs and often app-usage data; teams forget both. Cross-check the result against the Apple App Privacy answers — they must tell the same story.

Also required: **privacy policy URL** in the Console and accessible in-app, covering the developer entity, data handled, retention, and deletion procedure.

## Account deletion

Apps allowing account creation must offer:
1. an **in-app** path to request account and data deletion, and
2. a **web-accessible** deletion URL declared in the Play Console, reachable without reinstalling the app

Note the divergence from Apple: Apple requires in-app; Google requires in-app **and** a web link. RN teams who satisfy only one get caught by the other.

## Sensitive permissions

Every permission needs a runtime prompt with context and a genuine feature behind it. Play blocks or requires declarations for several:

| Permission | Rule |
|---|---|
| `ACCESS_BACKGROUND_LOCATION` | Requires Console declaration + video demo; only for features that need it while the app is closed. Frequently rejected. |
| `QUERY_ALL_PACKAGES` | Restricted; allowed only for a narrow set of use cases. Often pulled in transitively — check the **merged** manifest. |
| `MANAGE_EXTERNAL_STORAGE` | Restricted; use scoped storage / SAF instead. |
| `READ_SMS`, `RECEIVE_SMS`, `CALL_LOG` | Restricted; SMS-retriever API is the compliant path for OTP. |
| `READ_MEDIA_IMAGES` / `READ_MEDIA_VIDEO` | Photo/video permissions only for core functionality; otherwise use the **photo picker** (no permission needed). |
| `AD_ID` (`com.google.android.gms.permission.AD_ID`) | Must be declared if targeting API 33+ and using the advertising ID; must be absent for child-directed apps. |
| `POST_NOTIFICATIONS` | Runtime prompt on API 33+; requesting at launch with no context is a quality flag. |
| `RECORD_AUDIO`, `CAMERA` | Must map to a visible feature; background use needs a foreground service type. |
| Accessibility / `BIND_ACCESSIBILITY_SERVICE` | Only for genuine accessibility use; otherwise a suspension risk. |

```bash
# audit the MERGED manifest, not the source one
find android -path "*merged_manifests*" -name "AndroidManifest.xml" | head
```
RN libraries commonly add permissions you didn't request. `react-native-device-info` has historically pulled `READ_PHONE_STATE`; map libraries add location; several add `QUERY_ALL_PACKAGES`. Remove with `tools:node="remove"`:

```xml
<uses-permission android:name="android.permission.READ_PHONE_STATE" tools:node="remove"/>
```

## Photo and video permissions policy

Access to broad photo/video permissions is limited to apps where that access is core. One-off uploads (profile picture, document capture) must use the system photo picker or a document/camera intent.

```ts
// ✅ no permission needed
import * as ImagePicker from 'expo-image-picker';
await ImagePicker.launchImageLibraryAsync(); // uses the system picker on modern Android
```

## Age signals

Google's counterpart to Apple's Declared Age Range is the **Play Age Signals API** (`com.google.android.play:age-signals`, minSdk 23). It returns data only for users in jurisdictions with age-verification laws — US states with accountability acts, Brazil's Digital ECA (enforceable since 17 March 2026, which requires version 0.0.3 or higher).

Unlike Apple's, it needs no entitlement and no permission, so the integration cost is low. The compliance question is whether the app is in scope at all: 18+ content, or distribution into a regulated market. If the app also ships to iOS, the two APIs are separate integrations with different minimum OS versions — Apple's requires iOS 26 and an entitlement with lead time.

## Health and sensitive data

Health Connect data has its own restricted-use policy: no ads, no sale, no transfer to data brokers, explicit consent, and a privacy policy that discloses health-data handling specifically. See `health-and-regulated.md`.

## Device and network abuse

Covers the RN-specific hazards:
- No downloading executable code outside Play (same territory as Apple 2.5.2 — OTA JS updates are acceptable; delivering new native behavior is not)
- No self-modifying installers, no hidden background network use
- Cleartext traffic: `android:usesCleartextTraffic="true"` is a finding; use a network security config with domain-scoped exceptions if truly needed

```xml
<!-- 🟠 -->
<application android:usesCleartextTraffic="true">
```

## Secrets in the bundle

Same exposure as iOS — the JS bundle and `strings.xml` are extractable from the AAB. Google flags leaked API keys through Play Console's security advisories, and third-party key exposure can be treated as an abuse issue.

---

## Checklist

- [ ] Data safety form completed and consistent with the actual SDK inventory
- [ ] Data safety answers consistent with Apple App Privacy + `PrivacyInfo.xcprivacy`
- [ ] Privacy policy URL in Console and reachable in-app
- [ ] Account deletion available **in-app** and via a **public web URL** declared in Console
- [ ] Merged manifest audited; unused permissions removed with `tools:node="remove"`
- [ ] Background location declared and justified, or removed
- [ ] `QUERY_ALL_PACKAGES` / `MANAGE_EXTERNAL_STORAGE` / SMS permissions removed unless the use case qualifies
- [ ] Photo picker used instead of broad media permissions where access isn't core
- [ ] `AD_ID` declared if used; absent in child-directed apps
- [ ] Runtime permission prompts show context before the system dialog
- [ ] No cleartext traffic; network security config scoped if needed
- [ ] Health Connect data not used for ads or sold; disclosed in the policy
- [ ] No secrets in the JS bundle, `strings.xml`, or gradle properties shipped in the AAB
