# RN / Expo Package Map — Android Compliance Requirements

**Most React Native teams use the CLI (bare) workflow, so read the bare column first.** The Expo column applies to managed or prebuild projects. Both satisfy the same requirement — pick by project shape, not preference.

| Requirement | Policy | Expo | Bare React Native |
|---|---|---|---|
| In-app purchases | Play Billing | `react-native-purchases` (RevenueCat) via config plugin | `react-native-purchases` or `react-native-iap` |
| Secure credential / PHI storage | User Data | `expo-secure-store` | `react-native-keychain`, EncryptedSharedPreferences |
| Encrypted local database | User Data | `expo-sqlite` + app-layer encryption | `react-native-sqlcipher-storage`, `react-native-mmkv` with an encryption key |
| Photo access without broad media permission | Photo/video policy | `expo-image-picker` (system picker) | `react-native-image-picker` in picker mode |
| Document capture without storage permission | Photo/video policy | `expo-document-picker` | `react-native-document-picker` |
| Location with correct permission tier | Permissions | `expo-location` | `react-native-geolocation-service` |
| Background location (needs Console declaration + video) | Permissions | `expo-location` + `expo-task-manager` | `react-native-background-geolocation` |
| Foreground service with a declared type | Android 14+ | `expo-task-manager` (declare the type in the config plugin) | `react-native-background-actions`, `notifee` |
| Health Connect | Health data | `react-native-health-connect` via plugin | `react-native-health-connect` |
| Notifications with runtime permission (API 33+) | Permissions | `expo-notifications` | `@react-native-firebase/messaging`, `notifee` |
| Biometric re-auth | — | `expo-local-authentication` | `react-native-biometrics` |
| Screenshot protection (`FLAG_SECURE`) | PHI handling | `expo-screen-capture` | `react-native-screenguard` |
| OTA updates (scope-limited) | Device & Network Abuse | `expo-updates` | `react-native-code-push` |
| Edge-to-edge / insets (API 36) | Technical | `react-native-safe-area-context` | `react-native-safe-area-context` |
| Crash reporting with PII scrubbing | Data safety | `@sentry/react-native` with `beforeSend` | same |
| Secrets | Device & Network Abuse | server-side proxy; `expo-constants` only for non-secrets | server-side proxy; never `react-native-config` for secrets |

## Bare RN (CLI) — what you own that Expo would have generated

- **`ndkVersion` is pinned in your gradle.** 16 KB page alignment needs NDK r27+. Managed Expo doesn't expose this; you do, so it's both your problem and your fix.
- **`AndroidManifest.xml` is a real file you edit.** Permissions your dependencies merge in still won't appear there — build and check the merged manifest.
- **Signing config lives in `gradle.properties` or `build.gradle`.** The RN CLI template uses `MYAPP_RELEASE_STORE_PASSWORD` and friends; committing real values means anyone with repo access can sign as you. Use environment variables and gitignore `local.properties`.
- **`targetSdkVersion` is yours to raise**, and raising it to 36 makes edge-to-edge mandatory and stops `onBackPressed` firing. Budget layout and navigation work.

## Notes that change the recommendation

- **Version floors come from the wrapper.** The Play Billing Library major version is pinned by `react-native-iap` / `react-native-purchases`, and 16 KB page alignment is decided by the NDK each native dependency was built with. When either is behind Play's floor, upgrade the RN package — editing `android/app/build.gradle` usually just creates a version conflict.
- **`react-native-config` and `.env` are not secret storage.** Values land in the AAB in plaintext, and Play Console flags leaked keys through security advisories.
- **Expo config plugins generate the manifest.** Permissions, service declarations, and `foregroundServiceType` come from `app.json` plugin props. Audit the merged manifest after `expo prebuild` and a build, never the template.
- **Removing a transitive permission** is a manifest edit, not a package swap:
  ```xml
  <uses-permission android:name="android.permission.READ_PHONE_STATE" tools:node="remove"/>
  ```
  Add `xmlns:tools="http://schemas.android.com/tools"` to the `<manifest>` tag if it isn't there.
- **RevenueCat vs `react-native-iap`.** RevenueCat handles server-side purchase verification and cross-device entitlements, which removes both the client-trusted-entitlement finding and the cross-platform entitlement mismatch. `react-native-iap` is fine but you own the Play Developer API verification service.
