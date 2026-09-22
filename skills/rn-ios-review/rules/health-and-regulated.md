# Health, Medical & Other Regulated Apps (iOS)

Read this whenever the app touches health, fitness with medical framing, patient data, telehealth, clinical workflows, or insurance claims. Apple applies stricter rules here, and those rules are **separate from and additional to** regulatory obligations like HIPAA — passing review says nothing about being compliant, and being compliant says nothing about passing review. Report them as two distinct tracks.

## 1.4.1 / 1.4.2 — Physical harm

Medical apps providing dosage, diagnosis, or treatment guidance must identify their data sources and methodology, and the source must be qualified: the manufacturer, a hospital, a university, a health insurer, an FDA-approved body, or an equivalent. Apps that could cause harm through inaccuracy get extra scrutiny and may be asked for regulatory clearance.

Practical version: if a screen computes a clinical number, the app must say where the formula came from, in the UI, not just on the marketing site.

## 5.1.3 — Health and health research

- Health data collected through HealthKit or entered by the user must **not** be used for advertising, marketing, or similar use, and must **not** be sold or shared with data brokers.
- HealthKit data must **not** be written to iCloud.
- The app needs a privacy policy that specifically addresses health data handling — a generic policy is a rejection.
- Human-subject research requires ethics-committee approval, disclosure of that approval, and participant consent.

## HealthKit entitlement and purpose strings

HealthKit requires the entitlement plus `NSHealthShareUsageDescription` and `NSHealthUpdateUsageDescription`, and both must describe the *specific* clinical purpose.

```xml
<!-- 🟠 rejected -->
<string>We need access to your health data</string>

<!-- ✅ -->
<string>Read your step count and resting heart rate so your care team can review
activity trends between appointments.</string>
```

```ts
import AppleHealthKit from 'react-native-health';   // bare RN
// Expo: requires a config plugin + custom dev client.
// Verify the generated entitlements file after prebuild — the plugin's default
// purpose strings will not pass 5.1.1(ii).
```

## Demo accounts — the most common rejection for clinical apps

A provider-facing or patient-portal app can't be evaluated without credentials. Supply in App Store Connect review notes:

- a working demo account with realistic **synthetic** data (never real PHI)
- a short note explaining the clinical workflow the reviewer should follow
- any regulatory status (FDA clearance, CE mark, or "not a medical device")
- if the app needs a linked EHR or a paired device, a path that works without one

Missing or broken demo access is the single most common avoidable rejection in this category, and it costs a full review cycle each time.

## The HIPAA-adjacent layer (Apple does not check this — you must)

App Review does not validate HIPAA. But the same codebase facts drive both, so audit them in the same pass:

- **PHI at rest** — Keychain via `expo-secure-store` / `react-native-keychain`, or SQLCipher. Never `AsyncStorage`, never plain SQLite, never a JSON cache file.
- **PHI in transit** — TLS 1.2+, no `NSAllowsArbitraryLoads`, certificate pinning where the threat model calls for it.
- **PHI in logs and crash reports** — Sentry/Bugsnag/Crashlytics breadcrumbs routinely capture request bodies and navigation params containing patient identifiers. This is the most common real leak in RN healthcare apps, and it silently creates an App Privacy disclosure you never filed.
- **PHI in analytics** — event properties carrying MRN, DOB, or names. Same disclosure problem.
- **Screenshots and the app switcher** — obscure PHI on backgrounding with a privacy overlay (`expo-screen-capture`, or a blur view on `AppState` change).
- **Session handling** — inactivity timeout, biometric re-auth, token revocation on logout.
- **BAAs** — every third-party processor that can see PHI needs one. An SDK that sees PHI with no BAA is a finding regardless of what Apple says.
- **Deletion** — the in-app account deletion Apple requires (5.1.1(v)) has to interoperate with your retention obligations. State the retention period in the flow rather than silently keeping records.

```ts
// 🔴 leaks PHI into a third-party processor
Sentry.setContext('patient', { mrn, dob, name });
analytics().logEvent('view_record', { patientId, diagnosis });
console.log('claim payload', claim);

// ✅
Sentry.init({ beforeSend: scrubPHI, beforeBreadcrumb: scrubPHI });
analytics().logEvent('view_record', { recordType: 'lab' });
```

## Other regulated categories, briefly

- **Finance / lending (3.2.1)** — consumer loan APR capped at 36%; repayment terms of 60 days or less are prohibited. The developer entity must be the licensed operator or clearly disclose who is.
- **VPN (5.4)** — must use `NEVPNManager`, be offered by an enrolled organization, declare data collection, and must not sell or share data.
- **MDM (5.5)** — enterprise or education justification required; must not sell data.
- **Government / civic** — must be published by or on behalf of the government entity.

---

## Checklist

**Apple**
- [ ] Dosage or diagnostic content has a disclosed, qualified source, shown in-app
- [ ] HealthKit entitlement present; share and update purpose strings are clinically specific
- [ ] Health data not used for ads or marketing, not sold, not written to iCloud
- [ ] Privacy policy specifically covers health data
- [ ] Research features carry ethics approval and participant consent
- [ ] Demo account with synthetic data, plus a workflow note and regulatory status, in review notes
- [ ] In-app account deletion present (5.1.1(v))

**Regulatory — audit even though Apple doesn't**
- [ ] PHI encrypted at rest in Keychain/SecureStore/SQLCipher
- [ ] No PHI in logs, crash breadcrumbs, or analytics properties
- [ ] TLS enforced; no arbitrary-loads exception
- [ ] Privacy overlay on backgrounding
- [ ] Inactivity timeout and biometric re-auth
- [ ] BAA in place for every processor that can see PHI
- [ ] Deletion flow reconciled with retention obligations and disclosed to the user
