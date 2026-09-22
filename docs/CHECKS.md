# Check reference

Every finding the two scanners can emit. **Generated from the scanner source by `scripts/gen_checks.py`** — don't edit by hand; CI fails if this file drifts from the code.
**52 checks total.**


Severity meanings are in each skill's `SKILL.md`. In short: BLOCKER stops the release, HIGH is a commonly cited rejection or an enforcement risk, MEDIUM is reviewer discretion, LOW is polish.

Every check is a **lead, not a verdict**. Confirm each hit by reading the code around it — and note that a clean scan is not compliance, since the structural problems (moderation quality, whether a disclosure form matches the code, whether receipt validation really happens server-side) are not detectable by static analysis.

## iOS — 28 checks

`skills/rn-ios-review/scripts/scan.py`

| ID | Severity | App Store Review Guidelines | What it means |
|---|---|---|---|
| `DYNAMIC-CODE` | BLOCKER | 2.5.2 | Dynamic code execution — downloading or evaluating code is prohibited |
| `EXTERNAL-PAYMENT` | BLOCKER | 3.1.1 | Possible external payment path for digital goods — confirm the SKU is a physical good or real-world service before clearing |
| `ICON-NAME-MISSING` | BLOCKER | upload validation | CFBundleIconName is present but empty. The upload fails with |
| `MINING` | BLOCKER | 2.5.18 | Possible on-device cryptocurrency mining |
| `PRIVACY-POLICY` | BLOCKER | 5.1.1(i) | No privacy policy reference found in the app. A policy must be linked in App Store Connect |
| `PRIVATE-API` | BLOCKER | 2.5.1 | Possible private API usage in native code |
| `SECRET-HARDCODED` | BLOCKER | 1.6 / 2.5 | Possible hardcoded credential — the JS bundle ships in plaintext inside the IPA |
| `ACCOUNT-DELETION` | HIGH | 5.1.1(v) | Account creation found with no in-app deletion path. Deletion must be initiated |
| `ARBITRARY-LOADS` | HIGH | 1.6 | App Transport Security disabled — cleartext traffic allowed |
| `ATT-MISSING` | HIGH | 5.1.2 | Tracking / ads / analytics SDK present with no App Tracking Transparency request. |
| `ATT-STRING-MISSING` | HIGH | 5.1.2 | ATT is requested but NSUserTrackingUsageDescription was not found — the prompt will |
| `CLIENT-ENTITLEMENT` | HIGH | 2.5.13 | Purchase entitlement possibly trusted from local storage — validate the receipt server-side |
| `CRASH-PII` | HIGH | 5.1.1 / 5.1.2 | Personal data possibly sent to a crash or analytics processor — scrub before send and disclose in App Privacy |
| `INSECURE-STORAGE` | HIGH | 1.6 | Token or personal data in AsyncStorage (unencrypted on disk) — use SecureStore / Keychain |
| `PAYMENT-SDK` | HIGH | 3.1.1 | Third-party payment SDK present — must not serve digital goods on iOS |
| `PRIVACY-MANIFEST` | HIGH | Privacy manifests | No PrivacyInfo.xcprivacy found in the ios/ directory. The app target needs one declaring |
| `RESTORE-MISSING` | HIGH | 3.1.1 | IAP integration found with no restore-purchases path. Non-consumables and subscriptions |
| `TRACKING-SDK` | HIGH | 5.1.2 | Tracking / analytics / ads SDK — needs ATT before it initializes, plus matching App Privacy answers |
| `UGC-MODERATION` | HIGH | 1.2 | User-generated content features found with no report/block/moderation path. Apple requires |
| `BACKGROUND-MODES` | MEDIUM | 2.5.4 | Background modes declared — every entry must be genuinely used for its |
| `ENTITLEMENTS-REVIEW` | MEDIUM | 2.5.1 / 5.1.3 / 5.4 | Entitlements present that reviewers scrutinise: |
| `LOGIN-ALTERNATIVE` | MEDIUM | 4.8 | Third-party social login found with no privacy-preserving alternative. Offer a login that |
| `OTA-UPDATES` | MEDIUM | 2.3.1 / 2.5.2 | OTA update channel — permitted for fixes and content, not for shipping unreviewed features |
| `PRIVACY-MANIFEST-UNVERIFIED` | MEDIUM | Privacy manifests | No ios/ directory, so this looks like a managed Expo project and the privacy manifest |
| `REVIEW-PROMPT` | MEDIUM | 5.6.1 | Possible custom rating prompt — only the system StoreReview API is allowed |
| `WEBVIEW-SHELL` | MEDIUM | 4.2 | WebView usage — if it is the primary surface, the app may be judged a repackaged website |
| `CONSOLE-LOG` | LOW | Quality · PII leakage risk | console logging in source — strip from release paths and check it never logs personal data |
| `CROSS-PLATFORM-COPY` | LOW | 2.3.10 | Reference to another platform in user-facing copy |

## Android — 24 checks

`skills/rn-android-review/scripts/scan.py`

| ID | Severity | Play policy / Console requirement | What it means |
|---|---|---|---|
| `APK-NOT-AAB` | BLOCKER | App Bundle requirement | Release pipeline builds an APK (assemble) with no bundle task. Play requires an |
| `DYNAMIC-CODE` | BLOCKER | Device & Network Abuse | Dynamic code execution — downloading or executing code outside Play is prohibited |
| `EXTERNAL-PAYMENT` | BLOCKER | Payments | Possible external payment path for digital goods — confirm the SKU is a physical good or real-world service, |
| `PRIVACY-POLICY` | BLOCKER | User Data | No privacy policy reference found. A policy URL is required in Play Console and must be |
| `SECRET-HARDCODED` | BLOCKER | Device & Network Abuse | Possible hardcoded credential — the JS bundle and strings.xml are extractable from the AAB |
| `ACCOUNT-DELETION` | HIGH | Account deletion | Account creation found with no in-app deletion path. Play requires deletion available |
| `CLEARTEXT` | HIGH | Device & Network Abuse | Cleartext HTTP traffic enabled — use a scoped network security config if an exception is genuinely needed |
| `CLIENT-ENTITLEMENT` | HIGH | Payments | Purchase entitlement possibly trusted from local storage — verify the purchase token with the Play Developer API server-side |
| `CRASH-PII` | HIGH | Data safety | Personal data possibly sent to a crash or analytics processor — scrub before send and disclose in Data safety |
| `FGS-TYPE-MISSING` | HIGH | Android 14+ foreground services | Foreground service permission and a service declared, but no foregroundServiceType. |
| `INSECURE-STORAGE` | HIGH | User Data | Token or personal data in AsyncStorage (unencrypted on disk) — use EncryptedSharedPreferences / Keystore |
| `PAYMENT-SDK` | HIGH | Payments | Third-party payment SDK present — must not serve digital goods unless an alternative-billing program applies |
| `PERM-&lt;NAME&gt;` | HIGH/MEDIUM | Play permissions policy | 22 restricted or sensitive permissions detected in the manifest, each reported with why it is restricted — `ACCESS_BACKGROUND_LOCATION`,… |
| `PURCHASE-ACK` | HIGH | Payments | Billing integration found with no purchase acknowledgement or token verification. |
| `UGC-MODERATION` | HIGH | User Generated Content | UGC features found with no report/block/moderation path. Play requires a user agreement, |
| `ALLOW-BACKUP` | MEDIUM | User Data | android:allowBackup is enabled — app data can reach the user's cloud backup; disable or scope it if the app holds sensitive data |
| `DATA-SAFETY-INVENTORY` | MEDIUM | Data safety | SDKs that collect data: |
| `LOCAL-PROPERTIES-TRACKED` | MEDIUM | Quality | android/local.properties exists and is not in .gitignore. It holds machine- |
| `MERGED-MANIFEST-NOT-CHECKED` | MEDIUM | Permissions | Only the source manifest was scanned — no merged manifest found. Build the app and re-check |
| `OTA-UPDATES` | MEDIUM | Device & Network Abuse | OTA update channel — permitted for fixes and content, not for shipping unreviewed behavior |
| `TARGET-SDK-UNKNOWN` | MEDIUM | Target API level requirement | Could not determine targetSdkVersion — check the value resolved by the RN gradle plugin |
| `TRACKING-SDK` | MEDIUM | Data safety | Tracking / analytics / ads SDK — must appear in the Data safety form, and AD_ID must be declared if used |
| `WEBVIEW-SHELL` | MEDIUM | Spam & Minimum Functionality | WebView usage — if it is the primary surface, the app may be judged a repackaged website |
| `CONSOLE-LOG` | LOW | Quality · PII leakage risk | console logging in source — strip from release paths and check it never logs personal data |

