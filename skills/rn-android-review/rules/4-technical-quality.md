# Google Play — Technical & Quality Requirements

These are enforced at **upload time** by Play Console, not by a human reviewer. They fail the release rather than the review, so check them first — a team can fix every policy finding and still be unable to publish.

## Target API level

Play raises the floor every August. As of the **31 August 2026** step:

- **New apps and updates must target Android 16 (API level 36) or higher.** Below that, the upload is rejected.
- **Existing apps must target at least Android 15 (API 35)** to remain discoverable to users on newer OS versions; an app left below that doesn't disappear, it just stops being installable by new users on current devices — which looks exactly like organic decline.
- Extensions to 1 November of the same year can be requested in Play Console before the deadline.
- Wear OS / Android Automotive / TV / XR have their own, lower floors.

```bash
grep -rn "targetSdkVersion\|compileSdkVersion" android/build.gradle android/app/build.gradle
grep -rn "targetSdkVersion" app.json app.config.* 2>/dev/null   # Expo: expo-build-properties
```
Always confirm the current floor against the live requirements page — this number moves annually and a stale value in an audit is worse than no value.

**Raising targetSdk is not a one-line change in RN.** Expect:
- **Edge-to-edge is mandatory** on API 36; apps can no longer opt out. Layouts need `react-native-safe-area-context` (recent version) and insets verified on Android 15 and 16.
- **Predictive back**: `Activity.onBackPressed()` and `KEYCODE_BACK` no longer fire for API 36 apps. Navigation libraries and any custom back handling need the predictive-back APIs, or a temporary `android:enableOnBackInvokedCallback="false"` opt-out while migrating.
- Foreground service type enforcement, notification permission behavior, and per-app language changes all shift with recent levels.

## 16 KB page size support

Recent Android devices use 16 KB memory pages. Apps **targeting API 35+** on 64-bit devices must ship native libraries aligned for 16 KB. There is now a hard date: **from 1 February 2027, updates that do not support 16 KB page sizes cannot be released at all.** RN apps hit this through **native dependencies**: Hermes/JSC, Reanimated, MMKV, SQLite, camera, ML, and analytics SDKs with `.so` files.

```bash
# find native libs in the build output
find android -name "*.so" | head -50
```
Fix path: upgrade React Native and every native dependency to versions built with NDK r27+/16 KB alignment. A single stale `.so` from an unmaintained SDK blocks the whole release — identify it early, because replacing an abandoned dependency takes weeks.

## App Bundle format

Play requires AAB for new apps and updates. APK-only pipelines fail at upload.

```bash
grep -rn "bundleRelease\|assembleRelease" android/app/build.gradle fastlane/ .github/ 2>/dev/null
```

## Foreground services

Android 14+ requires a declared `foregroundServiceType` and a matching permission for each service, and Play requires a Console declaration justifying the use. RN background-task libraries (`react-native-background-actions`, `react-native-background-fetch`, background geolocation) create these.

**Geofencing was removed as an approved foreground-service use case** in the 15 April 2026 announcement — use the Geofence API instead. Compliance date **27 January 2027**. Any RN app pairing `react-native-background-geolocation` (or similar) with a `location` foreground service is on a deadline, and this is a regression risk for apps that were previously compliant.

```xml
<service android:name=".MyService"
         android:foregroundServiceType="location" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION"/>
```
An undeclared or mismatched type crashes at runtime on new devices and is a Play declaration violation.

## Android App Quality / core vitals

Play surfaces ANR and crash rates; exceeding the bad-behaviour thresholds reduces discoverability and can trigger warnings. The overall thresholds are a **user-perceived crash rate of 1.09%** and an **ANR rate of 0.47%** (per-device-model thresholds are higher: 8%/4% phone, 8%/5% watch). RN-specific causes:
- Heavy synchronous work on the JS thread blocking startup
- Large images decoded on the main thread
- Unbounded list rendering without `FlatList` windowing
- Blocking native module calls on the UI thread

## Other upload-time gates

- **Signing**: Play App Signing enrollment; keystore mismatch blocks the upload
- **Version code**: must increment
- **Permissions declarations form**: background location, SMS/call log, photo/video, accessibility, `QUERY_ALL_PACKAGES` each need a Console declaration when used
- **Content rating questionnaire**: must match actual content; a mismatch is a policy violation
- **Ads declaration**: must be set if the app contains ads
- **Government / financial / health app declarations** where applicable
- **Pre-launch report**: review its crash and accessibility findings before release; it surfaces device-specific RN crashes cheaply

---

## Checklist

- [ ] `targetSdkVersion` at or above Play's current floor for new uploads (verify live)
- [ ] Existing-app discoverability floor also met
- [ ] Edge-to-edge handled; insets verified on recent Android versions
- [ ] Predictive back migrated, or explicitly opted out during migration
- [ ] All native `.so` libraries 16 KB aligned; RN and native deps upgraded
- [ ] Release pipeline produces an AAB
- [ ] Every foreground service has a declared type, matching permission, and Console justification
- [ ] Permission declaration forms submitted for every restricted permission in the merged manifest
- [ ] Content rating questionnaire matches actual content
- [ ] Ads declaration set correctly
- [ ] Version code increments; Play App Signing configured
- [ ] Pre-launch report crashes triaged
- [ ] ANR/crash vitals within thresholds (crash < 1.09%, ANR < 0.47%)
- [ ] No geofencing via foreground service (deadline 27 Jan 2027)
- [ ] 16 KB alignment done (hard block from 1 Feb 2027)
