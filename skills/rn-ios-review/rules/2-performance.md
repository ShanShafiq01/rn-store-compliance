# Apple Section 2 — Performance

The section that catches RN apps hardest, because 2.5.x is about *how* the binary behaves and RN gives you several ways to violate it without noticing.

## Upload gates (before any of the guidelines below)

These fail in App Store Connect with no human review involved, the same way Play's gates do. Check them first:

| Gate | Requirement | How to check |
|---|---|---|
| Build SDK | Since **28 April 2026**, every new submission and update must be built with the iOS 26 / iPadOS 26 SDK (or later per that year's requirement) | Xcode version in CI; `IPHONEOS_DEPLOYMENT_TARGET` is a different setting — don't confuse them |
| Age rating questions | Responses to the updated age-rating questionnaire were due **31 Jan 2026**; without them App Store Connect blocks update submissions | App Information in App Store Connect |
| Privacy manifest | App target and third-party SDKs on Apple's list need `PrivacyInfo.xcprivacy` | see `5-legal.md` |
| Build number | Must increment | — |

For a React Native project the SDK floor is the expensive one: it usually forces an Xcode bump, which forces an RN version bump, which forces pod and native-module upgrades. Treat it as a scheduled project each spring, not a submission-day discovery.

## 2.1 App completeness

Submit the final version. No placeholders, no "coming soon" screens, no features behind a flag that reviewers can't reach. If login is required, supply a **demo account** in App Store Connect notes — for a healthcare or B2B app, this is the single most common avoidable rejection.

**RN evidence**
```ts
// 🔴
<Text>Coming soon</Text>
if (__DEV__) { /* the only path that works */ }
TODO: implement checkout
```
Also: every IAP must be submitted for review alongside the build, or the purchase flow "does nothing" from the reviewer's seat.

## 2.2 Beta testing

Demos, betas and trials belong in TestFlight, not the App Store. An app whose main screen says "beta" invites a rejection.

## 2.3 Accurate metadata

2.3.1 forbids hidden or undocumented features — including **any functionality unlocked remotely after review**. This is the OTA rule in disguise; see 2.5.2 below.

2.3.2–2.3.13: screenshots must show the app in use, description must match behavior, keywords must not name competitors, age rating must reflect the highest-rated content, and in-app events/subscriptions must be described accurately.

**RN evidence**: feature flags read from a remote config that gate whole product areas; `if (remoteConfig.getBoolean('enable_casino'))`. Flag any flag that changes what the app *is*.

## 2.4 Hardware compatibility

- 2.4.1 Support the target device natively; iPhone apps should run on iPad reasonably.
- 2.4.5 macOS-specific rules if shipping Catalyst.
- Excessive battery/heat: RN offenders are unthrottled `setInterval` polling, always-on location, and animation loops that never pause on background.

```ts
// 🟠 battery drain
setInterval(() => fetchFeed(), 1000);
Location.watchPositionAsync({ accuracy: Accuracy.BestForNavigation }); // with no stop()
```
Check `AppState` handling — timers and watchers should stop on `background`.

## 2.5 Software requirements

The dense one. Each sub-rule with its RN translation:

### 2.5.1 Public APIs only
No private API usage. In RN this arrives through native modules or old third-party pods.
```objc
NSSelectorFromString(@"_privateMethod")   // 🔴 BLOCKER
valueForKey:@"_internalState"
```
Grep native module sources and vendored pods, not just JS.

### 2.5.2 No downloading or executing code
```ts
eval(remoteString);                      // 🔴 BLOCKER
new Function(fetchedCode)();             // 🔴
require(dynamicPathFromServer);          // 🔴
```
**OTA updates are the nuanced case.** `expo-updates` and CodePush are permitted because they update the JS that is part of the reviewed app. They become a violation when they change the app's advertised purpose or add features/data collection not reviewed. Assess what the update channel actually ships: bug fixes and content = fine; a new payment flow = 2.3.1 + 2.5.2.

### 2.5.4 Background modes
Declared background modes must be used for their declared purpose. Audio background mode on an app with no audio is a rejection.
```xml
<!-- Info.plist: justify every entry -->
<key>UIBackgroundModes</key>
<array><string>location</string><string>audio</string></array>
```
In Expo, these come from `app.json` → `ios.infoPlist.UIBackgroundModes`.

### 2.5.6 Web content uses WebKit
`react-native-webview` is WebKit-backed on iOS — fine. Custom JS engines for browsing are not.

### 2.5.8 No alternate desktop or home-screen environments

### 2.2 No demo/trial/test versions; no "lite" stubs
(2.5.10 itself is "Intentionally omitted" in the current guidelines.)

### 2.5.13 Facial recognition for authentication
Account authentication using face matching must use **LocalAuthentication**, not ARKit,
Vision, or a third-party face model — and must offer an alternate method for users
under 13. In RN this means `react-native-biometrics` / `expo-local-authentication`,
not a `react-native-vision-camera` frame processor feeding a face-embedding model.

```ts
// 🔴 custom face matching for login
const embedding = await faceModel.run(frame); if (cosine(embedding, stored) > 0.9) signIn();
// ✅ LocalAuthentication via the OS
await LocalAuthentication.authenticateAsync({ promptMessage: 'Sign in' });
```

### 2.5.14 Recording and user activity logging
Recording, logging, or otherwise making a record of user activity requires **explicit
consent** and a **clear visual and/or audible indicator** while it happens. This covers
session-replay SDKs, screen recording, and background audio capture — all common in RN
via `react-native-record-screen` and analytics replay tools.

### 2.5.15 Apps that read/write files must handle iCloud/Files properly.

> Receipt validation is not a numbered 2.5 rule. Validate server-side anyway — a
> client-trusted entitlement flag is a 3.1.1 finding, not a 2.5 one:
> ```ts
> // 🔴 trusting the client
> if (await AsyncStorage.getItem('isPremium')) unlock();
> // ✅ server-side receipt / RevenueCat entitlement check
> ```

---

## Checklist

- [ ] No placeholders, TODO screens, or dev-only paths in the release build
- [ ] Demo credentials supplied in review notes if login is required
- [ ] All IAP products submitted with the build
- [ ] No "beta"/"trial" framing in the listing or UI
- [ ] No feature gated behind post-review remote flags that changes the app's purpose
- [ ] No private API usage in native modules or vendored pods
- [ ] No `eval` / `new Function` / dynamic `require` of remote code
- [ ] OTA channel ships fixes and content only, not new reviewed-surface features
- [ ] Every declared `UIBackgroundModes` entry is genuinely used
- [ ] Timers, location watchers, and animations stop on `AppState` background
- [ ] Purchases validated server-side, not by a local flag
- [ ] IPv6 tested (Apple's network is IPv6-only)
- [ ] No on-device mining
