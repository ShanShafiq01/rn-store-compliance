# RN / Expo Package Map — iOS Compliance Requirements

**Most React Native teams use the CLI (bare) workflow, so read the bare column first.** The Expo column applies to managed or prebuild projects. Both satisfy the same requirement — pick by project shape, not preference.

| Requirement | Guideline | Expo | Bare React Native |
|---|---|---|---|
| In-app purchases | 3.1.1 | `react-native-purchases` (RevenueCat) via config plugin | `react-native-purchases` or `react-native-iap` |
| App Tracking Transparency | 5.1.2 | `expo-tracking-transparency` | `react-native-tracking-transparency` |
| Secure credential / PHI storage | 1.6, 5.1.3 | `expo-secure-store` | `react-native-keychain` |
| Encrypted local database | 1.6 | `expo-sqlite` + app-layer encryption | `react-native-sqlcipher-storage`, `react-native-mmkv` with an encryption key |
| Sign in with Apple | 4.8 | `expo-apple-authentication` | `@invertase/react-native-apple-authentication` |
| Biometric re-auth | 1.6 | `expo-local-authentication` | `react-native-biometrics` |
| System review prompt | 5.6.1 | `expo-store-review` | `react-native-store-review` / `InAppReview` |
| Location with correct permission tier | 5.1.5 | `expo-location` | `react-native-geolocation-service` |
| Background location (justify the mode) | 2.5.4, 5.1.5 | `expo-location` + `expo-task-manager` | `react-native-background-geolocation` |
| HealthKit | 5.1.3 | `react-native-health` via custom dev client | `react-native-health` |
| Notifications | 4.5.4 | `expo-notifications` | `@react-native-firebase/messaging`, `notifee` |
| OTA updates (scope-limited) | 2.3.1, 2.5.2 | `expo-updates` | `react-native-code-push` |
| Screenshot / app-switcher protection | 5.1.3 (PHI) | `expo-screen-capture` | `react-native-screenguard`, or a blur view on `AppState` |
| Crash reporting with PII scrubbing | 5.1.1, 5.1.2 | `@sentry/react-native` with `beforeSend` | same |
| Secrets | 1.6, 2.5 | server-side proxy; `expo-constants` only for non-secrets | server-side proxy; never `react-native-config` for secrets |

## Bare RN (CLI) — what you own that Expo would have generated

- **`ios/Podfile.lock` is your SDK inventory.** Apple requires third-party SDKs on its commonly-used list to ship a privacy manifest and signature. A stale pod that lacks one fails validation at upload, and the error names the pod, not the RN package that pulled it in. Audit the lock file, not just `package.json`.
- **Purpose strings live in a real `Info.plist` you edit directly.** No config plugin defaults to inherit, which means no vague-string surprises — and no excuse for one.
- **Entitlements are a file you maintain.** An entitlement with no matching feature is a rejection; check `*.entitlements` against what the app actually does before every submission.
- **The deployment target in the Podfile decides which pod versions resolve.** An old target silently pins old pods, which is how projects end up without privacy manifests.
- **The build SDK is your Xcode version.** Apple's floor (iOS 26 SDK since 28 Apr 2026) is an upload gate; in bare RN that means an Xcode bump, which usually means an RN bump and a pod migration. Plan it, don't discover it.

## Notes that change the recommendation

- **`react-native-config` and `.env` are not secret storage.** Values land in the IPA in plaintext. Anything that must stay secret goes behind your own backend.
- **RevenueCat vs `react-native-iap`.** RevenueCat handles server-side receipt validation and cross-device entitlements, removing three separate rejection causes at once (2.5.13 client-trusted purchases, missing restore, 3.1.2 cross-device access). `react-native-iap` is fine but you own the validation service.
- **Expo config plugins generate the native config.** Purpose strings, entitlements, and `UIBackgroundModes` come from `app.json` plugin props. Audit the output of `expo prebuild`, not the template — plugin defaults ship vague purpose strings that fail 5.1.1(ii).
- **ATT placement beats ATT presence.** The package is easy; the ordering is what gets rejected. `requestTrackingPermissionsAsync()` must resolve before any tracking SDK initializes, which for most RN analytics modules means before their import executes.
