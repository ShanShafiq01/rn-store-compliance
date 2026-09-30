# Check reference

Every finding the two scanners can emit. **Generated from the scanner source by `scripts/gen_checks.py`** — don't edit by hand; CI fails if this file drifts from the code.
**84 checks total.**


Severity meanings are in each skill's `SKILL.md`. In short: BLOCKER stops the release, HIGH is a commonly cited rejection or an enforcement risk, MEDIUM is reviewer discretion, LOW is polish.

Every check is a **lead, not a verdict**. Confirm each hit by reading the code around it — and note that a clean scan is not compliance, since the structural problems (moderation quality, whether a disclosure form matches the code, whether receipt validation really happens server-side) are not detectable by static analysis.

## iOS — 48 checks

`skills/rn-ios-review/scripts/scan.py`

| ID | Severity | App Store Review Guidelines | What it means |
|---|---|---|---|
| `DYNAMIC-CODE` | BLOCKER | 2.5.2 | Dynamic code execution — downloading or evaluating code is prohibited |
| `EXTERNAL-PAYMENT` | BLOCKER | 3.1.1 | Possible external payment path for digital goods. Check the storefront before treating this as a blocker: under 3.1.1(a) no entitlement is… |
| `HEALTH-DATA-TO-ADS` | BLOCKER | 5.1.2(vi) / 2.5.18 / 5.1.3(i) | A health value appears to flow into an analytics or advertising |
| `ICON-NAME-MISSING` | BLOCKER | upload validation | CFBundleIconName is present but empty. The upload fails with |
| `MEDIA-DOWNLOADER` | BLOCKER | 5.2.3 | Third-party media downloader. 5.2.3 bars the ability to save, convert or download media |
| `MINING` | BLOCKER | 2.4.2 / 3.1.5(ii) | Possible on-device cryptocurrency mining |
| `PRIVACY-POLICY` | BLOCKER | 5.1.1(i) | No privacy policy reference found in the app. A policy must be linked in App Store Connect |
| `PRIVATE-API` | BLOCKER | 2.5.1 | Possible private API usage in native code |
| `SECRET-HARDCODED` | BLOCKER | 1.6 / 2.5 | Possible hardcoded credential — the JS bundle ships in plaintext inside the IPA |
| `SENSOR-ONLY-VITALS` | BLOCKER | 1.4.1 | Possible claim to measure a vital sign using only device |
| `UIWEBVIEW` | BLOCKER | 2.5.1 / upload validation | Deprecated UIWebView found in {len(hits)} vendored file(s). Apple rejects |
| `ACCOUNT-DELETION` | HIGH | 5.1.1(v) | Account creation found with no in-app deletion path. Deletion must be initiated |
| `AD-REPORT-MISSING` | HIGH | 2.5.18 | Ads are displayed with no in-app ad-reporting control found. |
| `ARBITRARY-LOADS` | HIGH | 1.6 | App Transport Security disabled — cleartext traffic allowed |
| `ATT-MISSING` | HIGH | 5.1.2 | Tracking / ads / analytics SDK present with no App Tracking Transparency request. |
| `ATT-STRING-MISSING` | HIGH | 5.1.2 | ATT is requested but NSUserTrackingUsageDescription was not found — the prompt will |
| `CLIENT-ENTITLEMENT` | HIGH | 3.1.1 | Purchase entitlement possibly trusted from local storage — validate the receipt server-side |
| `CRASH-PII` | HIGH | 5.1.1 / 5.1.2 | Personal data possibly sent to a crash or analytics processor — scrub before send and disclose in App Privacy |
| `FRAMEWORK-UNUSED` | HIGH | 2.1 | The {framework} framework is linked but no {label} integration |
| `HEALTHKIT-PERM-UNUSED` | HIGH | 2.1 / 5.1.1 | HealthKit types requested but no read or write found for them: |
| `IAP-UNFINISHED-TRANSACTION` | HIGH | 2.3.2 / 2.1 | StoreKit purchases are made but no finishTransaction call was |
| `INSECURE-STORAGE` | HIGH | 1.6 | Token or personal data in AsyncStorage (unencrypted on disk) — use SecureStore / Keychain |
| `MEDICAL-NO-DISCLAIMER` | HIGH | 1.4.1 | Health app surfaces medical language with no disclaimer found. |
| `PAYMENT-SDK` | HIGH | 3.1.1 | Third-party payment SDK present — must not serve digital goods on iOS |
| `PRIVACY-MANIFEST` | HIGH | Privacy manifests | No PrivacyInfo.xcprivacy found in the ios/ directory. The app target needs one declaring |
| `PRIVACY-MANIFEST-EMPTY` | HIGH | 5.1.1 / 5.1.2 | PrivacyInfo.xcprivacy declares NSPrivacyCollectedDataTypes as an empty |
| `RESTORE-MISSING` | HIGH | 3.1.1 | IAP integration found with no restore-purchases path. Non-consumables and subscriptions |
| `SIWA-REDUNDANT-PROFILE` | HIGH | 4 (Design) / HIG | Sign in with Apple is present alongside a profile-completion |
| `SOCIAL-REVOKE-MISSING` | HIGH | 5.1.1(v) | Social login present with no revocation path. 5.1.1(v) requires a |
| `TRACKING-SDK` | HIGH | 5.1.2 | Tracking / analytics / ads SDK — needs ATT before it initializes, plus matching App Privacy answers |
| `UGC-BLOCK-MISSING` | HIGH | 1.2 | User-generated content with reporting but no self-service block. |
| `UGC-MODERATION` | HIGH | 1.2 | User-generated content features found with no report/block/moderation path. Apple requires |
| `BACKGROUND-MODES` | MEDIUM | 2.5.4 | Background modes declared — every entry must be genuinely used for its |
| `ENTITLEMENTS-REVIEW` | MEDIUM | 2.5.1 / 5.1.3 / 5.4 | Entitlements present that reviewers scrutinise: |
| `LOGIN-ALTERNATIVE` | MEDIUM | 4.8 | Third-party social login found with no privacy-preserving alternative. Offer a login that |
| `MAPS-KEY-RESTRICTION` | MEDIUM | Device & Network Abuse | Google API (AIza) key in source. These are client keys — they ship in the binary by |
| `MEDICAL-NO-CITATION` | MEDIUM | 1.4.1 | Medical or health information with no citations found. 1.4.1 |
| `OTA-UPDATES` | MEDIUM | 2.3.1 / 2.5.2 | OTA update channel — permitted for fixes and content, not for shipping unreviewed features |
| `POD-PRIVACY-MANIFESTS` | MEDIUM | Privacy manifests | {len(third_party)} third-party pods in Podfile.lock. Any SDK on Apple's |
| `PRIVACY-MANIFEST-UNVERIFIED` | MEDIUM | Privacy manifests | No ios/ directory, so this looks like a managed Expo project and the privacy manifest |
| `REVIEW-PROMPT` | MEDIUM | 5.6.1 | Possible custom rating prompt — only the system StoreReview API is allowed |
| `SUBSCRIPTION-COPY-MISMATCH` | MEDIUM | 3.1.1 / 3.1.3(e) | In-app copy says 'subscription' but no IAP library is present. |
| `UGC-COMMENT-REPORT-MISSING` | MEDIUM | 1.2 | Posts can be reported but comments appear not to be. Every |
| `WEBVIEW-SHELL` | MEDIUM | 4.2 | WebView usage — if it is the primary surface, the app may be judged a repackaged website |
| `CONSOLE-LOG` | LOW | Quality · PII leakage risk | console logging in source — strip from release paths and check it never logs personal data |
| `CROSS-PLATFORM-COPY` | LOW | 2.3.10 | Reference to another platform in user-facing copy |
| `DEPLOYMENT-TARGET-OLD` | varies | 2.4.1 | iOS deployment target is {value}. |
| `PURPOSE-STRING` | varies | 5.1.1(ii) | Purpose string problem — |

## Android — 36 checks

`skills/rn-android-review/scripts/scan.py`

| ID | Severity | Play policy / Console requirement | What it means |
|---|---|---|---|
| `ABI-NO-64BIT` | BLOCKER | 64-bit requirement | Native ABIs are restricted to {', '.join(sorted(set(declared)))} with no |
| `AGP-TOO-OLD` | BLOCKER | App Bundle requirement / Target API level | Android Gradle Plugin {major}.{minor} is too old to ship. |
| `APK-NOT-AAB` | BLOCKER | App Bundle requirement | Release pipeline builds an APK (assemble) with no bundle task. Play requires an |
| `BILLING-VERSION` | BLOCKER | Play Billing Library deprecation | Play Billing Library {bill.group(1)}.x detected; the floor moved to |
| `DYNAMIC-CODE` | BLOCKER | Device & Network Abuse | Dynamic code execution — downloading or executing code outside Play is prohibited |
| `EXTERNAL-PAYMENT` | BLOCKER | Payments | Possible external payment path for digital goods — confirm the SKU is a physical good or real-world service, |
| `PRIVACY-POLICY` | BLOCKER | User Data | No privacy policy reference found. A policy URL is required in Play Console and must be |
| `SECRET-HARDCODED` | BLOCKER | Device & Network Abuse | Possible hardcoded credential — the JS bundle and strings.xml are extractable from the AAB |
| `ACCOUNT-DELETION` | HIGH | Account deletion | Account creation found with no in-app deletion path. Play requires deletion available |
| `AI-CONTENT-NO-REPORT` | HIGH | AI-Generated Content | A generative model is called with no in-app reporting or flagging |
| `CLEARTEXT` | HIGH | Device & Network Abuse | Cleartext HTTP traffic enabled — use a scoped network security config if an exception is genuinely needed |
| `CLIENT-ENTITLEMENT` | HIGH | Payments | Purchase entitlement possibly trusted from local storage — verify the purchase token with the Play Developer API server-side |
| `CRASH-PII` | HIGH | Data safety | Personal data possibly sent to a crash or analytics processor — scrub before send and disclose in Data safety |
| `FGS-TYPE-MISSING` | HIGH | Android 14+ foreground services | Foreground service permission and a service declared, but no foregroundServiceType. |
| `HEALTH-PERM-UNUSED` | HIGH | Health Connect restricted data | Health Connect permissions declared with no matching read found |
| `INSECURE-STORAGE` | HIGH | User Data | Token or personal data in AsyncStorage (unencrypted on disk) — use EncryptedSharedPreferences / Keystore |
| `KEYSTORE-COMMITTED` | HIGH | Device & Network Abuse | {len(keystores)} signing keystore(s) tracked in git. Combined with a password |
| `NDK-VERSION` | HIGH | 16 KB page size support | ndkVersion is {m.group(1)}. NDK r28+ aligns to 16 KB by default. |
| `PAYMENT-SDK` | HIGH | Payments | Third-party payment SDK present — must not serve digital goods unless an alternative-billing program applies |
| `PERM-&lt;NAME&gt;` | HIGH/MEDIUM | Play permissions policy | 22 restricted or sensitive permissions detected in the manifest, each reported with why it is restricted — `ACCESS_BACKGROUND_LOCATION`,… |
| `PURCHASE-ACK` | HIGH | Payments | Billing integration found with no purchase acknowledgement or token verification. |
| `SIGNING-SECRET-COMMITTED` | HIGH | Device & Network Abuse | A signing credential appears to be hardcoded in {label}. Anyone with the |
| `UGC-MODERATION` | HIGH | User Generated Content | UGC features found with no report/block/moderation path. Play requires a user agreement, |
| `ALLOW-BACKUP` | MEDIUM | User Data | android:allowBackup is enabled — app data can reach the user's cloud backup; disable or scope it if the app holds sensitive data |
| `BILLING-VERIFY` | MEDIUM | Play Billing Library deprecation | Billing wrapper present — confirm the pinned Play Billing Library major version meets |
| `DATA-SAFETY-INVENTORY` | MEDIUM | Data safety | SDKs that collect data: |
| `LOCAL-PROPERTIES-TRACKED` | MEDIUM | Quality | android/local.properties exists and is not in .gitignore. It holds machine- |
| `MAPS-KEY-RESTRICTION` | MEDIUM | Device & Network Abuse | Google API (AIza) key in source. These are client keys — they ship in the binary by |
| `MERGED-MANIFEST-NOT-CHECKED` | MEDIUM | Permissions | Only the source manifest was scanned — no merged manifest found. Build the app and re-check |
| `OTA-UPDATES` | MEDIUM | Device & Network Abuse | OTA update channel — permitted for fixes and content, not for shipping unreviewed behavior |
| `PAGE-SIZE-16KB` | MEDIUM | 16 KB page size support | {len(sos)} native library file(s) in the build output. Each must be built for 16 KB page |
| `TARGET-SDK-UNKNOWN` | MEDIUM | Target API level requirement | Could not determine targetSdkVersion — check the value resolved by the RN gradle plugin |
| `TRACKING-SDK` | MEDIUM | Data safety | Tracking / analytics / ads SDK — must appear in the Data safety form, and AD_ID must be declared if used |
| `WEBVIEW-SHELL` | MEDIUM | Spam & Minimum Functionality | WebView usage — if it is the primary surface, the app may be judged a repackaged website |
| `CONSOLE-LOG` | LOW | Quality · PII leakage risk | console logging in source — strip from release paths and check it never logs personal data |
| `TARGET-SDK` | varies | Target API level requirement | targetSdkVersion is {target}. New uploads and updates need API |

